# AI Code Audit Log: NetArchitect (CIC-307)

**Team:** Manan Sharma & Anurag Pandey
**AI tool used:** Claude (Anthropic) was used to scaffold the codebase, presets and configuration templates from the assignment specification.
**Our role:** We acted as Lead Network Architects and Validators. We reviewed every generated rule against packet flow, standards and the test oracle (Python's `ipaddress` module).

This log records **real defects that came out of the AI-generated draft** of this project. Nothing here was staged. Each incident gives:

- the prompt or context
- the buggy output, kept verbatim where it is a fixture
- a packet-flow analysis
- the fix
- the regression test that keeps the fix in place

Addresses are the real ones allocated by the tool for the presets.

| # | Area | Severity | Caught by | Status |
|---|------|----------|-----------|--------|
| 1 | Campus `PROTECT-MGMT` ACL: wrong direction semantics, no return path | **High**: locks out the network operations team | Manual packet-flow review of the generated config | Fixed, plus a new automated checker |
| 2 | WAN `IOT-SEGMENT` ACL: default-deny without DNS | **High**: all 2,000 IoT devices fail to reach the cloud | Packet-flow walk of a device boot sequence | Fixed, plus a checker rule |
| 3 | MAN `COLO-PROTECT` ACL: no return traffic for colo-initiated sessions | Medium | The checker built for incident 1 | Fixed |
| 4 | Minor AI hallucinations in the media and IPsec engines | Low | Code review | Fixed |

---

## Incident 1: Management-VLAN ACL filters the wrong direction (Campus LAN)

### Prompt / context
We gave the AI the assignment spec and asked it to complete the project. While generating `presets/campus_lan.json` it was building a "protect the management VLAN" policy. The policy was to be applied on the core switch's `interface Vlan99` SVI.

### AI-generated code (buggy)
Preset rules (kept verbatim in `tests/fixtures/ai_v1_protect_mgmt.json`):
```json
[{"action":"permit","proto":"ip", "src":"NET-MGMT","dst":"any","remark":"mgmt hosts"},
 {"action":"permit","proto":"tcp","src":"SERVERS", "dst":"any","dport":22,"remark":"jump host SSH"},
 {"action":"permit","proto":"udp","src":"SERVERS", "dst":"any","dport":161,"remark":"SNMP poller"},
 {"action":"deny",  "proto":"ip", "src":"any",     "dst":"any","remark":"everything else","log":true}]
```
Rendered IOS (with the real allocation: NET-MGMT 10.10.11.192/27, SERVERS 10.10.11.128/26):
```
ip access-list extended PROTECT-MGMT
 permit ip 10.10.11.192 0.0.0.31 any
 permit tcp 10.10.11.128 0.0.0.63 any eq 22
 permit udp 10.10.11.128 0.0.0.63 any eq 161
 deny ip any any log
interface Vlan99
 ip access-group PROTECT-MGMT out
```

### Technical analysis: packet flow
An ACL applied **`out`** on an SVI only sees packets that the switch **routes into** VLAN 99. The destination of every such packet is a host in 10.10.11.192/27. The source is always *outside* that subnet, because traffic between two hosts in the same VLAN is switched at L2 and never reaches the gateway.

Walk an SSH session from NMS workstation **10.10.11.200** (VLAN 99) to the edge router's loopback **10.10.11.227**:

| Step | Packet | Interface / direction | ACL result |
|---|---|---|---|
| 1 | SYN 10.10.11.200:51000 → 10.10.11.227:22 | enters `Vlan99` **in** | no inbound ACL, so routed to EDGE-RTR1 ✔ |
| 2 | SYN-ACK 10.10.11.227:22 → 10.10.11.200:51000 | routed into `Vlan99` **out** | rule 1: is the src in 10.10.11.192/27? **No** (the src is .227). Rules 2–3: is the src in SERVERS? No. Rule 4: **deny ip any any log** ✘ |

The TCP handshake never completes. The one host group the policy meant to privilege, the network admins, cannot manage any device outside its own VLAN.

- **Rule 1 is dead code.** Its source (NET-MGMT) can never appear on outbound traffic of its own SVI.
- **Rules 2–3 used `dst any`.** On an outbound filter the destination is *always* inside VLAN 99, so `any` hid the intent.
- **No return path existed**: there was no `established` or source-port rule.

**Second defect, found during the fix.** The AI's first correction wrote the SNMP rule as `permit udp SERVERS eq 161 NET-MGMT`. That puts port 161 as the *source* port. An NMS in SERVERS polling a device in VLAN 99 sends to **destination** port 161, so that rule would also never match a poll. We corrected it to `permit udp SERVERS NET-MGMT eq 161`, and separately allowed SNMP *responses* (`udp any eq 161 → NET-MGMT`) for NMS hosts that sit inside VLAN 99.

### Final fix
```
ip access-list extended PROTECT-MGMT
 permit tcp 10.10.11.128 0.0.0.63 10.10.11.192 0.0.0.31 eq 22      ! jump host -> mgmt
 permit udp 10.10.11.128 0.0.0.63 10.10.11.192 0.0.0.31 eq 161     ! SNMP polls
 permit tcp any 10.10.11.192 0.0.0.31 established                  ! replies to admin sessions
 permit udp any eq 161 10.10.11.192 0.0.0.31                       ! SNMP replies to NMS
 permit udp 10.10.11.128 0.0.0.63 eq 53 10.10.11.192 0.0.0.31      ! DNS replies
 permit icmp any 10.10.11.192 0.0.0.31                             ! ping/traceroute replies
 deny ip any 10.10.11.192 0.0.0.31 log
```
Re-walk step 2: SYN-ACK to 10.10.11.200 has the ACK flag set, so it matches `established` ✔.

**Systemic fix:** we added `netarchitect/acl_audit.py`, a static packet-flow checker that runs before any config is emitted. It flags:
1. rules whose src (for `in`) or dst (for `out`) cannot be inside the VLAN;
2. rules whose *other* side is inside the VLAN, i.e. intra-VLAN traffic that never crosses the gateway;
3. outbound default-deny ACLs with no `established` or source-port return rule.

**Regression test:** `tests/test_engine.py::test_ai_v1_mgmt_acl_is_flagged_dead` loads the verbatim AI rules and asserts that the build is rejected with the "never crosses the gateway" and "replies to sessions opened BY hosts" findings.

---

## Incident 2: IoT segmentation ACL silently blocks DNS (Global WAN)

### Prompt / context
This was the same generation run, for the Global WAN preset. The requirement was to segment 2,000 IoT sensors and scanners, so that IoT devices may only talk to the cloud MQTT broker and HTTPS telemetry endpoints in the AWS VPC (10.100.0.0/16), with no lateral movement into the enterprise.

### AI-generated code (buggy)
```
ip access-list extended IOT-SEGMENT
 permit udp any any eq 67                                   ! DHCP
 permit tcp 10.50.2.0 0.0.1.255 10.100.0.0 0.0.255.255 eq 8883
 permit tcp 10.50.2.0 0.0.1.255 10.100.0.0 0.0.255.255 eq 443
 deny ip 10.50.2.0 0.0.1.255 10.50.0.0 0.0.255.255 log
 deny ip any any
interface GigabitEthernet0/0.30
 ip access-group IOT-SEGMENT in
```
The DHCP pool generated for VLAN 30 hands out `dns-server 1.1.1.1`, because the WAN preset has no internal DNS server.

### Technical analysis: packet flow
Follow the boot sequence of sensor **10.50.2.50** that connects to `mqtt.<broker>.example`:

| Step | Packet | ACL `IOT-SEGMENT in` on Gi0/0.30 |
|---|---|---|
| 1 | DHCPDISCOVER 0.0.0.0:68 → 255.255.255.255:67 | rule 1 permit ✔ (lease obtained, DNS = 1.1.1.1) |
| 2 | DNS query 10.50.2.50:5353 → **1.1.1.1:53** (UDP) | rules 2–3: is the dst in 10.100/16? No. Rule 4: is the dst in 10.50/16? No. Rule 5: **deny ip any any** ✘ |
| 3 | MQTT CONNECT to the broker IP | **never sent**: the name never resolves |

The ACL *reads* correctly in review because port 8883 is explicitly permitted. Functionally, though, every device that uses an FQDN (the normal case for cloud brokers) fails, and the drop counter on the implicit deny is the only symptom. This is a classic "least privilege broke a dependency" bug: the AI treated the application flow as the whole flow and forgot the name-resolution step that comes before it.

### Final fix
```
 permit udp any any eq 67
 permit udp 10.50.2.0 0.0.1.255 any eq 53      ! DNS resolution for broker FQDN
 permit tcp 10.50.2.0 0.0.1.255 10.100.0.0 0.0.255.255 eq 8883
 ...
```
Re-walk step 2: the query matches the new rule ✔. The reply comes back *outbound* on Gi0/0.30, where no ACL is applied ✔.

**Possible hardening (documented, not applied):** point the DHCP `dns-server` at the VPC's AmazonProvidedDNS resolver (VPC base + 2 = 10.100.0.2) and narrow the rule to `host 10.100.0.2 eq 53`. That would also stop DNS tunnelling to arbitrary resolvers.

**Systemic fix:** `acl_audit.py` now flags any inbound default-deny ACL that has no UDP/53 permit.
**Regression test:** `test_ai_v1_iot_acl_without_dns_is_flagged`.

---

## Incident 3: Colo ACL drops replies to sessions the trading servers open (Metro MAN)

The automated checker from incident 1 rejected the AI's own Metro MAN preset the first time it ran. `COLO-PROTECT` (applied `out` on the colo trading VLAN 10.20.4.0/27) permitted specific HQ sources and then denied everything else. The trading servers open their own outbound sessions: NTP for trade timestamping, DNS, and market-data feeds. The replies to those sessions are routed *into* VLAN 40, hit the final deny, and are dropped.

**Packet:** NTP reply from 162.159.200.1:123 → 10.20.4.10:123 is filtered `out` on Gi0/0.40. No rule matches, so `deny ip any any log` drops it ✘.
**Fix:** added `permit tcp any 10.20.4.0 0.0.0.31 established`, `permit udp any eq 123 …` and a DNS-reply rule from HQ-SERVERS. The checker now passes, and `test_presets_pass_acl_audit[man]` guards it.

---

## Incident 4: Minor AI hallucinations caught in review

| Where | AI output | Problem | Fix |
|---|---|---|---|
| `media.py`, carrier long-haul branch | Always emitted `10GBASE-LR SFP+ at carrier NID`, even for 1 Gb/s WAN circuits | A 10G optic will not link with a 1000BASE carrier NID port: the speed and PCS layers don't match | Optic chosen by bandwidth: `1000BASE-LX SFP` for ≤ 1 Gb/s |
| `engine.py`, IPsec rationale | "MSS clamped so ESP+GRE overhead never fragments" | The design uses a route-based VTI (`tunnel mode ipsec ipv4`), which has **no GRE header**. The text describes a different technology | Reworded to "ESP + outer-IP tunnel overhead" |

---

## Defences we kept against AI hallucinations
- **Independent oracle:** 40 randomized VLSM allocations and every prefix from /0 to /32 are cross-checked against Python's `ipaddress` module (`tests/test_vlsm.py`). The bitwise code is never trusted on its own.
- **Explicit 32-bit masking:** `~mask & 0xFFFFFFFF` everywhere, with a test asserting that the wildcard is never negative. In Python `~0xFFFFFF00 == -4294967041`, a common AI slip.
- **Config invariants:** tests assert that no trunk uses `allowed vlan all`, that every trunk has `nonegotiate`, that every OSPF `network`/wildcard pair matches an allocated subnet, and that every ACL wildcard is a valid inverse mask.
- **Physics boundaries:** 100 / 100.01 / 101 / 400 / 401 m and the optical-margin sweep up to 80 km are tested explicitly.
