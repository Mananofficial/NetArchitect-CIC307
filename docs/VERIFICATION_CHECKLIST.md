# Packet Tracer Verification Checklist (with expected results)

Run each command and compare against **Expected**. Save each screenshot into `screenshots/` under the name shown.

## A. Campus LAN (`exports/campus_lan/*.cfg`)

**Devices:**
- CORE-SW1 = 3650-24PS. Add an AC-POWER-SUPPLY in the Physical tab first.
- BLDG-A-ACC1, BLDG-B-ACC1, BLDG-C-ACC1 = 2960-24TT
- EDGE-RTR1 = ISR4331
- DHCP-SRV = Server-PT

**Cabling (copper straight-through):**

| CORE-SW1 port | Connects to |
|---|---|
| Gi1/0/1 | BLDG-A-ACC1 Gi0/1 |
| Gi1/0/2, Gi1/0/3 | BLDG-B-ACC1 Gi0/1, Gi0/2 |
| Gi1/0/4, Gi1/0/5 | BLDG-C-ACC1 Gi0/1, Gi0/2 |
| Gi1/0/10 | DHCP-SRV |
| Gi1/0/24 | EDGE-RTR1 Gi0/0/0 |

**Extra lines on CORE-SW1** (for the server port):
```
conf t
interface Gi1/0/10
 switchport mode access
 switchport access vlan 60
 spanning-tree portfast
end
```

**DHCP-SRV settings:**
- IP 10.10.11.138, mask 255.255.255.192, gateway 10.10.11.129, DNS 10.10.11.138
- Services → DHCP → On. Add a pool with these values, then click **Add**:
  - name `STAFF-B`
  - default gateway 10.10.2.1
  - DNS 10.10.11.138
  - start IP 10.10.2.20
  - subnet mask 255.255.254.0
  - max users 400

**PC-B1:** plug into BLDG-B-ACC1 Fa0/1 and set IP Configuration to DHCP.

| # | Where / command | Expected | Screenshot |
|---|---|---|---|
| A1 | Whole canvas | 5 network devices + server + PC, all link lights green (STP may take ~30 s) | `campus_topology.png` |
| A2 | CORE-SW1 `show vlan brief` | VLANs 10,11,12,20,30,40,50,60,99,998,999 | `campus_vlans.png` |
| A3 | CORE-SW1 `show interfaces trunk` | Gi1/0/1, Po1, Po2 trunking; native 999; allowed lists = 10,20,30,40,50,60,99 / 11,20,30,40,50,99 / 12,20,30,40,50,99 | `campus_trunks.png` |
| A4 | CORE-SW1 `show etherchannel summary` | Po1(SU) with Gi1/0/2(P) Gi1/0/3(P); Po2(SU) with Gi1/0/4(P) Gi1/0/5(P); protocol LACP | `campus_lacp.png` |
| A5 | CORE-SW1 `show spanning-tree vlan 11` | "This bridge is the root", priority 4107 (4096 + VLAN 11) | `campus_stp_root.png` |
| A6 | CORE-SW1 `show ip ospf neighbor` | 1 neighbour 10.10.11.227 (EDGE-RTR1), state FULL | `campus_ospf.png` |
| A7 | EDGE-RTR1 `show ip route ospf` | O routes for 10.10.0.0/23 … 10.10.11.192/27 via 10.10.11.224 | `campus_edge_routes.png` |
| A8 | PC-B1 `ipconfig` | 10.10.2.x / 255.255.254.0, gateway 10.10.2.1 | `campus_dhcp.png` |
| A9 | PC-B1 `ping 10.10.2.1` then `ping 10.10.11.138` | replies (first ping may lose 1 packet to ARP) | `campus_ping.png` |

The Packet Tracer CLI may print `% Invalid input` for `crypto key generate rsa modulus 2048`, `ip ssh version 2`, or for `write memory` when run in config mode. These do not affect the network, so ignore them.

## B. Metro MAN (`exports/metro_man/*.cfg`)

**Devices:** HQ-RTR1, REMA-RTR1, REMB-RTR1 and COLO-RTR1 are all **Router-PT-Empty**. Power each one off and insert **PT-ROUTER-NM-1CGE** modules:
- HQ: slots 0–6
- the other three: slots 0–2

**Cabling:**

| Link | A side | B side |
|---|---|---|
| Primary to REMOTE-A | HQ Gi1/0 | REMA Gi1/0 |
| Secondary (EVPL) to REMOTE-A | HQ Gi2/0 | REMA Gi2/0 |
| Primary to REMOTE-B | HQ Gi3/0 | REMB Gi1/0 |
| Secondary (EVPL) to REMOTE-B | HQ Gi4/0 | REMB Gi2/0 |
| Primary to COLO | HQ Gi5/0 | COLO Gi1/0 |
| Secondary (EVPL) to COLO | HQ Gi6/0 | COLO Gi2/0 |

**LAN at HQ and at REMOTE-A:**
1. Router Gi0/0 → a 2960 switch.
2. On that switch's router-facing port: `switchport mode trunk`.
3. Plug a PC into the switch and configure its port with `switchport mode access` and `switchport access vlan 10`.
4. Set the PC to DHCP. The router itself is the DHCP server.

The Packet Tracer CLI will reject the `bfd …` lines and the `policy-map` / `service-policy` QoS lines. That is expected: they are valid IOS but outside PT's feature set.

| # | Where / command | Expected | Screenshot |
|---|---|---|---|
| B1 | Canvas | 4 routers, 6 inter-site links, 2 LAN switches + 2 PCs | `man_topology.png` |
| B2 | HQ-RTR1 `show ip ospf neighbor` | **6 neighbours FULL**: 10.20.2.212 ×2, 10.20.3.212 ×2, 10.20.4.52 ×2 | `man_ospf_neighbors.png` |
| B3 | HQ-RTR1 `show ip ospf border-routers` / `show ip protocols` | HQ is ABR for areas 0, 1, 2 | `man_abr.png` |
| B4 | REMA-RTR1 `show ip route ospf` | `O IA 10.20.3.0/24` (REMOTE-B summary, one route not three); HQ routes via **10.20.2.208** (primary, cost 10) | `man_summary_routes.png` |
| B5 | HQ PC `ipconfig` | 10.20.0.x, gateway 10.20.0.1 | `man_hq_dhcp.png` |
| B6 | HQ PC `ping 10.20.2.11` (or whatever IP the REMA PC got) | replies | `man_ping.png` |
| B7 | **Failover:** HQ-RTR1 `conf t` / `int g1/0` / `shutdown`, then REMA-RTR1 `show ip route ospf`, then repeat the ping | HQ routes now via **10.20.2.210** (secondary EVPL, cost 100); ping still works after reconvergence | `man_failover.png` |
| B8 | HQ-RTR1 `int g1/0` / `no shutdown` | traffic returns to 10.20.2.208 | (optional) |

Save the files as `exports/campus_lan.pkt` and `exports/metro_man.pkt`.

## C. Global WAN
Packet Tracer cannot run IKEv2/IPsec VTI or the eBGP session to the cloud. Submit `exports/global_wan_configs.txt` as the verification export for this profile; the README explains it is intended for GNS3 (CSR1000v / IOSv). If you build the three branch-to-Delhi links in PT using the same Router-PT method as section B, OSPF areas 0–3 and the `area range` summaries can still be shown there.
