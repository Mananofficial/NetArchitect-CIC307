# NetArchitect: Recommendation & Config Engine

**CIC-307 Computer Networks Mini-Project**
**Team:** Manan Sharma · Anurag Pandey

NetArchitect is a Python command-line tool for planning a network. It takes a preset or custom network description (JSON), runs a set of algorithmic rule engines, and produces three things:

- an **infrastructure recommendation**: media, transceivers, VLSM plan, routing protocol and topology tier;
- **copy-paste-ready Cisco IOS configurations** for switches, routers, SVIs and ACLs;
- an **architectural rationale log** that explains *why* every choice was made, with the numbers and the IEEE/RFC references behind it.

```
 Input Ingestion        L1/L2 Media Engine        L3 VLSM & Routing          Explainable Exporter
 preset / custom JSON -> distance & bandwidth  -> bitwise subnet allocator -> IOS configs + rationale log
 loader.py (validate)    media.py                 vlsm.py, routing.py         configgen.py, exporter.py
                                    \___________ explain.py (RationaleLog) __________/
                                                 acl_audit.py (packet-flow checks before export)
```

## Quick start
Requires Python 3.10 or newer. The engine has no third-party dependencies; only `pytest` is needed to run the tests.

```bash
pip install -r requirements.txt          # installs pytest
python -m netarchitect --list-presets
python -m netarchitect --preset campus                   # report to stdout
python -m netarchitect --preset all --export exports     # regenerate all verification exports
python -m netarchitect --preset man --show-config        # print device configs
python -m netarchitect --config examples/custom_two_site.json --export out
python -m netarchitect --check-link 150 --media copper   # -> PhysicalDistanceViolationError, exit 1
python -m netarchitect --check-link 22000                # OS2 + optical budget rationale
python -m netarchitect --vlsm 192.168.0.0/24 --hosts 100 50 20 2
python -m pytest -v                                      # 205 tests
```

## The three preset profiles
| Preset | Scenario | Key outputs |
|---|---|---|
| `campus` | 3 buildings (< 400 m), 1,600 endpoints, PoE APs | Cat6a drops; 2×10G OM4 10GBASE-SR LACP backbones; 9 VLANs + 802.1Q pruned trunks; Rapid-PVST+ with the core as root; collapsed core; OSPF Area 0; NAT edge; guest and management ACLs |
| `man` | HQ + 2 remote sites (15 km, 35 km) + FinTech colo (22 km), 450 users | OS2 SMF with 10GBASE-ER / 10G-ZR chosen by optical budget (with attenuator check); diverse EVPL secondary paths; sub-5 ms RTT verification; multi-area OSPF with summarization; BFD; LLQ QoS (EF / AF41) |
| `wan` | Delhi, Mumbai, Bengaluru, Chennai + AWS VPC, 2,000 IoT/scanners | Carrier circuits; hierarchical per-city summary blocks; multi-area OSPF (Areas 0–3) with `area range`; IKEv2/IPsec VTI; eBGP to the cloud (AS65050↔AS64512) with prefix-lists and a Null0 anchor; IoT segmentation ACL |

Custom input uses the same JSON schema (see `netarchitect/presets/*.json` and `examples/`). The validator checks:

- distance and bandwidth (> 0, finite)
- density (endpoints and APs)
- resiliency (`dual-homed` requires 2 links per remote site)
- VLAN range, reserved VLANs (1, 1002–1005) and native-VLAN collisions
- root prefix host bits
- cloud/enterprise address overlap
- link endpoints

## Decision rules (as implemented)
| Domain | Condition | Output |
|---|---|---|
| L1 media | run ≤ 100 m | Cat6a / 10GBASE-T (IEEE 802.3an 100 m channel) |
| | 100 m < run ≤ 400 m | OM4 / 10GBASE-SR at 850 nm (modal-dispersion limit, 2.9 dB channel budget) |
| | run > 400 m | OS2. Tries LR (1310 nm, 6.2 dB) → ER (1550 nm, 11.1 dB) → ZR (24 dB) and takes the first optic whose *loss + 3 dB margin ≤ budget*. Then checks receiver overload and recommends an attenuator if needed |
| | > 80 km | Carrier circuit with an LX/LR handoff. Explicitly requesting `smf` raises `OpticalBudgetError` |
| Boundary | copper requested > 100 m | `PhysicalDistanceViolationError` (signal attenuation warning). Same for MMF requested > 400 m |
| Bandwidth | > 10 Gb/s | ceil(bw / 10) member links in an LACP (802.1AX) bundle |
| VLSM | root prefix + host list | Requests are sorted by block size (largest first), aligned bitwise (`(cur + size − 1) & ~(size − 1)`) and allocated with zero overlap. /31 for point-to-point links (RFC 3021), /32 for loopbacks. Reports utilization and raises `AddressSpaceExhaustedError` when the space runs out |
| Hierarchical | multi-site | One power-of-two block per site, so each area is summarized by a single `area range` |
| Routing | 1 site and < 50 subnets | OSPF Area 0 |
| | multi-site or ≥ 50 subnets | Multi-area OSPF, HQ = Area 0 with ABR summarization |
| | cloud boundary | eBGP over IPsec (RFC 4271 / 6996) |
| Topology | campus ≤ 3 buildings and ≤ 2,000 endpoints | Collapsed core. Otherwise three-tier, hub-and-spoke MAN (dual-homed if resiliency requires it), or a hub-and-spoke WAN with a cloud transit |

Every decision writes a `Rationale` entry, rendered in `exports/<profile>_report.md`. Example:

> **HQ-COLO-PRIMARY → OS2 SMF / 10GBASE-ER**: Selected OS2 Single-Mode Fiber because link distance (22 km) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber. Optical budget for 10GBASE-ER @1550 nm: Tx(min) −4.7 dBm − Rx sensitivity −15.8 dBm = 11.1 dB. Plant loss = 22 km × 0.25 dB/km + 2 connectors × 0.5 dB + splices = 6.9 dB, leaving 4.20 dB (≥ 3.0 dB required margin).

## Deliverables in this repository
| Requirement | Location |
|---|---|
| Source code, CLI, explainability engine | `netarchitect/` |
| Unit tests (pytest) | `tests/`: 205 tests covering distance violations, address exhaustion, wildcard masks for /0–/32, randomized overlap fuzzing against `ipaddress`, routing selection, config invariants and ACL packet-flow regressions |
| AI Code Audit Report | `ai_audit_log.md` |
| Verification exports (3 profiles) | `exports/campus_lan_configs.txt`, `exports/metro_man_configs.txt`, `exports/global_wan_configs.txt`, plus per-device `.cfg` files, a report `.md` and a plan `.json` for each |

## Loading the exports in Packet Tracer / GNS3
Each `exports/<profile>/<HOST>.cfg` starts with `enable` / `configure terminal`. Open the device's **CLI** tab and paste the whole file.

**Campus (Packet Tracer):**
- `CORE-SW1` = 3650-24PS (add a power supply)
- `BLDG-x-ACC1` = 2960-24TT
- `EDGE-RTR1` = ISR4331

Cabling:
- CORE Gi1/0/1 → A-ACC Gi0/1
- CORE Gi1/0/2-3 → B-ACC Gi0/1-2
- CORE Gi1/0/4-5 → C-ACC Gi0/1-2
- CORE Gi1/0/24 → EDGE Gi0/0/0

To verify:
- `show vlan brief`, `show interfaces trunk` and `show etherchannel summary`
- `show spanning-tree root`, `show ip ospf neighbor` and `show ip route`
- put a PC on Fa0/1 with DHCP pointed at a server at 10.10.11.138 in VLAN 60

**MAN / WAN:** use `Router-PT` (or ISR4331) and add `NM-1CGE` modules so the interfaces are named `GigabitEthernet1/0`, `2/0`, … as in the interface map in each report. Connect each site's `Gi0/0` to a 2960 trunk carrying that site's VLANs. To verify, run `show ip ospf neighbor`, `show ip route ospf` (look for the `area range` summaries) and `show ip ospf border-routers`.

**Platform notes (be ready to explain these):**
- Packet Tracer's IOS subset does not support **BFD**, **IKEv2/VTI** or parts of **MQC QoS**. Those lines are rejected in PT but are valid IOS/IOS-XE. Run the WAN profile in **GNS3** (CSR1000v / IOSv) for the IPsec + BGP section, or accept the rejected lines in PT and demonstrate OSPF there.
- Packet Tracer does not accept RFC 3021 **/31** point-to-point addresses, which real IOS does. In the PT build, the CORE-SW1 ↔ EDGE-RTR1 link was readdressed to the free /30 10.10.12.0/30 (.1 core, .2 edge) so OSPF could form. The exported configs keep the /31, which is correct for real hardware.
- The 10G optics and 10GBASE-T are what the engine *recommends* for the real build. PT models only offer 1G ports, so the bandwidth is emulated.
- All `CHANGE-ME` secrets must be replaced. Public IPs use the RFC 5737 documentation ranges.

## Verification evidence
- `docs/VERIFICATION_CHECKLIST.md`: every Packet Tracer check with its expected result
- `screenshots/`: Packet Tracer screenshots (campus: VLANs, trunks, LACP, STP root, OSPF, DHCP, ping; MAN: OSPF neighbours, inter-area summaries, failover from primary to EVPL)
- `exports/campus_lan.pkt`, `exports/metro_man.pkt`: the Packet Tracer files
- **Global WAN:** `exports/global_wan_configs.txt` is intended for **GNS3** (CSR1000v / IOSv), because Packet Tracer cannot run IKEv2/IPsec VTI or eBGP to a cloud gateway. Its OSPF multi-area design is identical in structure to the MAN profile verified in Packet Tracer.

## Project structure
```
netarchitect/
  loader.py      preset loading + parameter validation
  media.py       L1/L2 media & transceiver engine (optical budget, overload, LACP)
  vlsm.py        bitwise VLSM, hierarchical site blocks, wildcard math
  routing.py     OSPF single/multi-area, eBGP, topology tier
  engine.py      orchestrator -> Plan (latency, density/PoE, L2 and QoS rationale)
  acl_audit.py   static packet-flow audit of ACLs (built from AI audit incident 1)
  configgen.py   Cisco IOS generator (VLANs, trunks, RSTP, LACP, SVIs, OSPF, BGP, IPsec, QoS, NAT, DHCP, ACLs)
  exporter.py    config bundle, per-device files, Markdown report, plan JSON
  explain.py     RationaleLog
  presets/       campus_lan.json, metro_man.json, global_wan.json
tests/           pytest suite + fixtures (verbatim AI-buggy ACL)
examples/        custom valid + deliberately invalid input
exports/         generated verification configs and reports
ai_audit_log.md
```

## Viva prep: likely questions
- **Why /31 on the point-to-point links?** RFC 3021: a two-node link needs no network or broadcast address, so a /31 saves half the space of a /30.
- **Why is the wildcard `~mask & 0xFFFFFFFF`?** Python integers are unbounded, so `~mask` alone is negative. A /23 gives mask 255.255.254.0 → wildcard 0.0.1.255.
- **Why ER rather than LR at 15 km?** LR's reach is 10 km. ER's budget is 11.1 dB and the loss is 4.95 dB, so the margin is fine. But Tx(max) of 4 dBm − 4.95 dB = −0.95 dBm is above the −1 dBm overload point, so we add a 2 dB attenuator.
- **Why ZR at 35 km when ER is rated for 40 km?** Reach is not the same as budget. 10.35 dB of loss plus 3 dB of margin is 13.35 dB, which exceeds ER's 11.1 dB.
- **Why multi-area OSPF in the MAN when there are fewer than 50 subnets?** The sites are geographically separate. Areas contain SPF churn from flapping metro links, and the ABR advertises one Type-3 summary per site.
- **Why the Null0 route on the WAN hub?** The BGP `network` command only advertises a prefix that exists *exactly* in the RIB. The Null0 anchor (AD 254) keeps the /16 aggregate present, while longer OSPF routes still win.
- **Why native VLAN 999 and `nonegotiate`?** They defeat double-tag VLAN hopping and DTP trunk negotiation by hosts.
- **What did the AI get wrong?** See `ai_audit_log.md`: an outbound SVI ACL that could never match, plus no return path; an IoT ACL that blocked DNS; missing return traffic in the colo ACL; a 10G optic chosen for a 1G circuit; and GRE described in a VTI rationale.
