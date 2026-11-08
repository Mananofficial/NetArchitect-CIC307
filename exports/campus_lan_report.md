# NetArchitect Design Report - Campus LAN - 3 buildings, 1,600 endpoints

- **Profile:** campus_lan
- **Root prefix:** 10.10.0.0/16
- **Topology tier:** Collapsed core (2-tier: core/distribution + access)
- **Routing:** OSPF single-area
- **Devices configured:** CORE-SW1, BLDG-A-ACC1, BLDG-B-ACC1, BLDG-C-ACC1, EDGE-RTR1

## Physical media & transceivers

| Link | Distance | Media | Transceiver | Lanes | Loss / Budget (dB) | Attenuator |
|---|---|---|---|---|---|---|
| BLDG-A horizontal drop | 90 m | Cat6a U/FTP | 10GBASE-T (RJ45) | 1 | - | - |
| CORE-SW1 <-> BLDG-A uplink | 45 m | Cat6a U/FTP | 10GBASE-T (RJ45) | 1 | - | - |
| BLDG-B horizontal drop | 95 m | Cat6a U/FTP | 10GBASE-T (RJ45) | 1 | - | - |
| CORE-SW1 <-> BLDG-B uplink | 180 m | OM4 MMF (50/125 um) | 10GBASE-SR SFP+ | 2 | 1.54 / 2.9 | - |
| BLDG-C horizontal drop | 100 m | Cat6a U/FTP | 10GBASE-T (RJ45) | 1 | - | - |
| CORE-SW1 <-> BLDG-C uplink | 340 m | OM4 MMF (50/125 um) | 10GBASE-SR SFP+ | 2 | 2.02 / 2.9 | - |
| CORE-SW1 <-> EDGE-RTR1 | 15 m | Cat6a U/FTP | 10GBASE-T (RJ45) | 1 | - | - |

## VLSM allocation

| Name | Site | VLAN | CIDR | Mask | Wildcard | Gateway | Broadcast | Hosts req/usable | Util % |
|---|---|---|---|---|---|---|---|---|---|
| STAFF-A | - | 10 | 10.10.0.0/23 | 255.255.254.0 | 0.0.1.255 | 10.10.0.1 | 10.10.1.255 | 480/510 | 94.1 |
| STAFF-B | - | 11 | 10.10.2.0/23 | 255.255.254.0 | 0.0.1.255 | 10.10.2.1 | 10.10.3.255 | 380/510 | 74.5 |
| STAFF-C | - | 12 | 10.10.4.0/23 | 255.255.254.0 | 0.0.1.255 | 10.10.4.1 | 10.10.5.255 | 300/510 | 58.8 |
| VOICE | - | 20 | 10.10.6.0/23 | 255.255.254.0 | 0.0.1.255 | 10.10.6.1 | 10.10.7.255 | 300/510 | 58.8 |
| WIFI-CORP | - | 30 | 10.10.8.0/23 | 255.255.254.0 | 0.0.1.255 | 10.10.8.1 | 10.10.9.255 | 400/510 | 78.4 |
| GUEST-WIFI | - | 40 | 10.10.10.0/24 | 255.255.255.0 | 0.0.0.255 | 10.10.10.1 | 10.10.10.255 | 250/254 | 98.4 |
| AP-MGMT | - | 50 | 10.10.11.0/25 | 255.255.255.128 | 0.0.0.127 | 10.10.11.1 | 10.10.11.127 | 90/126 | 71.4 |
| SERVERS | - | 60 | 10.10.11.128/26 | 255.255.255.192 | 0.0.0.63 | 10.10.11.129 | 10.10.11.191 | 40/62 | 64.5 |
| NET-MGMT | - | 99 | 10.10.11.192/27 | 255.255.255.224 | 0.0.0.31 | 10.10.11.193 | 10.10.11.223 | 24/30 | 80.0 |
| CORE-EDGE-P2P | - | - | 10.10.11.224/31 | 255.255.255.254 | 0.0.0.1 | 10.10.11.224 | - | 2/2 | 100.0 |
| LO-CORE-SW1 | - | - | 10.10.11.226/32 | 255.255.255.255 | 0.0.0.0 | 10.10.11.226 | - | 1/1 | 100.0 |
| LO-EDGE-RTR1 | - | - | 10.10.11.227/32 | 255.255.255.255 | 0.0.0.0 | 10.10.11.227 | - | 1/1 | 100.0 |

## Interface map

| Link | A side | B side | Transit |
|---|---|---|---|
| CORE-SW1 <-> BLDG-A uplink | CORE-SW1 GigabitEthernet1/0/1 | BLDG-A-ACC1 GigabitEthernet0/1 | 802.1Q trunk |
| CORE-SW1 <-> BLDG-B uplink | CORE-SW1 Port-channel1 | BLDG-B-ACC1 Port-channel1 | 802.1Q trunk |
| CORE-SW1 <-> BLDG-C uplink | CORE-SW1 Port-channel2 | BLDG-C-ACC1 Port-channel1 | 802.1Q trunk |
| CORE-SW1 <-> EDGE-RTR1 | CORE-SW1 GigabitEthernet1/0/24 | EDGE-RTR1 GigabitEthernet0/0/0 | 10.10.11.224/31 |

## Architectural rationale log

### Topology

- **Profile 'campus_lan' → Collapsed core (2-tier: core/distribution + access)**  
  3 buildings and 1600 endpoints on one campus: a separate distribution layer would add a switch pair per building without improving fault isolation. The L3 core switch acts as distribution, terminating every VLAN's SVI, while access switches stay pure L2 with RSTP.  
  _Refs: Cisco SAFE/Campus design guides_

### L1 Media

- **BLDG-A horizontal drop → Cat6a / 10GBASE-T**  
  Run of 90 m is within the 100 m 10GBASE-T channel limit (90 m permanent link + 10 m cords). Cat6a's 500 MHz rating supports 10 Gb/s over the full length and carries IEEE 802.3bt PoE (up to 90 W) for APs, phones and cameras; fiber would add transceiver cost with no reach benefit.  
  _Refs: IEEE 802.3an, IEEE 802.3bt, ANSI/TIA-568.2-D_
- **CORE-SW1 <-> BLDG-A uplink → Cat6a / 10GBASE-T**  
  Run of 45 m is within the 100 m 10GBASE-T channel limit (90 m permanent link + 10 m cords). Cat6a's 500 MHz rating supports 10 Gb/s over the full length and carries IEEE 802.3bt PoE (up to 90 W) for APs, phones and cameras; fiber would add transceiver cost with no reach benefit.  
  _Refs: IEEE 802.3an, IEEE 802.3bt, ANSI/TIA-568.2-D_
- **BLDG-B horizontal drop → Cat6a / 10GBASE-T**  
  Run of 95 m is within the 100 m 10GBASE-T channel limit (90 m permanent link + 10 m cords). Cat6a's 500 MHz rating supports 10 Gb/s over the full length and carries IEEE 802.3bt PoE (up to 90 W) for APs, phones and cameras; fiber would add transceiver cost with no reach benefit.  
  _Refs: IEEE 802.3an, IEEE 802.3bt, ANSI/TIA-568.2-D_
- **CORE-SW1 <-> BLDG-B uplink → OM4 MMF / 10GBASE-SR**  
  Run of 180 m exceeds the 100 m copper limit (IEEE 802.3an) but is within the 400 m reach of 10GBASE-SR on OM4. At 850 nm the low-cost VCSEL source is limited by modal dispersion, not loss; OM4's 4700 MHz*km effective modal bandwidth sustains 10 Gb/s to 400 m. Channel loss 1.54 dB (0.180 km x 3.0 dB/km + 2 x 0.5 dB connectors) <= 2.9 dB SR budget.  
  _Refs: IEEE 802.3ae, TIA-492AAAD (OM4), TIA-568.3-D_
- **BLDG-C horizontal drop → Cat6a / 10GBASE-T**  
  Run of 100 m is within the 100 m 10GBASE-T channel limit (90 m permanent link + 10 m cords). Cat6a's 500 MHz rating supports 10 Gb/s over the full length and carries IEEE 802.3bt PoE (up to 90 W) for APs, phones and cameras; fiber would add transceiver cost with no reach benefit.  
  _Refs: IEEE 802.3an, IEEE 802.3bt, ANSI/TIA-568.2-D_
- **CORE-SW1 <-> BLDG-C uplink → OM4 MMF / 10GBASE-SR**  
  Run of 340 m exceeds the 100 m copper limit (IEEE 802.3an) but is within the 400 m reach of 10GBASE-SR on OM4. At 850 nm the low-cost VCSEL source is limited by modal dispersion, not loss; OM4's 4700 MHz*km effective modal bandwidth sustains 10 Gb/s to 400 m. Channel loss 2.02 dB (0.340 km x 3.0 dB/km + 2 x 0.5 dB connectors) <= 2.9 dB SR budget.  
  _Refs: IEEE 802.3ae, TIA-492AAAD (OM4), TIA-568.3-D_
- **CORE-SW1 <-> EDGE-RTR1 → Cat6a / 10GBASE-T**  
  Run of 15 m is within the 100 m 10GBASE-T channel limit (90 m permanent link + 10 m cords). Cat6a's 500 MHz rating supports 10 Gb/s over the full length and carries IEEE 802.3bt PoE (up to 90 W) for APs, phones and cameras; fiber would add transceiver cost with no reach benefit.  
  _Refs: IEEE 802.3an, IEEE 802.3bt, ANSI/TIA-568.2-D_

### Density

- **BLDG-A → 14 x 48-port access switches**  
  650 endpoints / 48 ports = 14 switches (2 stack(s); StackWise max 9 members). 30 PoE APs x 30 W (IEEE 802.3at Class 4) = 900 W PoE budget, so PoE+ capable access switches are required; IP phones share the PC port via the voice VLAN.  
  _Refs: IEEE 802.3at, IEEE 802.3bt_
- **BLDG-B → 11 x 48-port access switches**  
  520 endpoints / 48 ports = 11 switches (2 stack(s); StackWise max 9 members). 30 PoE APs x 30 W (IEEE 802.3at Class 4) = 900 W PoE budget, so PoE+ capable access switches are required; IP phones share the PC port via the voice VLAN.  
  _Refs: IEEE 802.3at, IEEE 802.3bt_
- **BLDG-C → 9 x 48-port access switches**  
  430 endpoints / 48 ports = 9 switches (1 stack(s); StackWise max 9 members). 25 PoE APs x 30 W (IEEE 802.3at Class 4) = 750 W PoE budget, so PoE+ capable access switches are required; IP phones share the PC port via the voice VLAN.  
  _Refs: IEEE 802.3at, IEEE 802.3bt_

### L2 Bundling

- **CORE-SW1 <-> BLDG-B uplink → LACP 2 x 10G**  
  Required bandwidth 20 Gb/s exceeds a single 10G lane; ceil(20/10) = 2 member links are bundled with LACP so traffic is hashed across them and a member failure only reduces capacity.  
  _Refs: IEEE 802.1AX_
- **CORE-SW1 <-> BLDG-C uplink → LACP 2 x 10G**  
  Required bandwidth 20 Gb/s exceeds a single 10G lane; ceil(20/10) = 2 member links are bundled with LACP so traffic is hashed across them and a member failure only reduces capacity.  
  _Refs: IEEE 802.1AX_

### VLSM

- **STAFF-A → 10.10.0.0/23**  
  480 hosts + 2 (network, broadcast) = 482 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.10.0.1 (first usable), broadcast 10.10.1.255. Utilization 480/510 = 94.1%.  
  _Refs: RFC 950, RFC 1878_
- **STAFF-B → 10.10.2.0/23**  
  380 hosts + 2 (network, broadcast) = 382 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.10.2.1 (first usable), broadcast 10.10.3.255. Utilization 380/510 = 74.5%.  
  _Refs: RFC 950, RFC 1878_
- **STAFF-C → 10.10.4.0/23**  
  300 hosts + 2 (network, broadcast) = 302 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.10.4.1 (first usable), broadcast 10.10.5.255. Utilization 300/510 = 58.8%.  
  _Refs: RFC 950, RFC 1878_
- **VOICE → 10.10.6.0/23**  
  300 hosts + 2 (network, broadcast) = 302 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.10.6.1 (first usable), broadcast 10.10.7.255. Utilization 300/510 = 58.8%.  
  _Refs: RFC 950, RFC 1878_
- **WIFI-CORP → 10.10.8.0/23**  
  400 hosts + 2 (network, broadcast) = 402 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.10.8.1 (first usable), broadcast 10.10.9.255. Utilization 400/510 = 78.4%.  
  _Refs: RFC 950, RFC 1878_
- **GUEST-WIFI → 10.10.10.0/24**  
  250 hosts + 2 (network, broadcast) = 252 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.10.10.1 (first usable), broadcast 10.10.10.255. Utilization 250/254 = 98.4%.  
  _Refs: RFC 950, RFC 1878_
- **AP-MGMT → 10.10.11.0/25**  
  90 hosts + 2 (network, broadcast) = 92 addresses; smallest power of two >= that is 2^7 = 128 -> /25 (mask 255.255.255.128, wildcard 0.0.0.127). Gateway 10.10.11.1 (first usable), broadcast 10.10.11.127. Utilization 90/126 = 71.4%.  
  _Refs: RFC 950, RFC 1878_
- **SERVERS → 10.10.11.128/26**  
  40 hosts + 2 (network, broadcast) = 42 addresses; smallest power of two >= that is 2^6 = 64 -> /26 (mask 255.255.255.192, wildcard 0.0.0.63). Gateway 10.10.11.129 (first usable), broadcast 10.10.11.191. Utilization 40/62 = 64.5%.  
  _Refs: RFC 950, RFC 1878_
- **NET-MGMT → 10.10.11.192/27**  
  24 hosts + 2 (network, broadcast) = 26 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.10.11.193 (first usable), broadcast 10.10.11.223. Utilization 24/30 = 80.0%.  
  _Refs: RFC 950, RFC 1878_
- **CORE-EDGE-P2P → 10.10.11.224/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-CORE-SW1 → 10.10.11.226/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **LO-EDGE-RTR1 → 10.10.11.227/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **campus root 10.10.0.0/16 → 12 subnets, 3044 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 3044 of 65536 addresses consumed (4.6% of the block); host efficiency 2268/3026 usable = 75.0%. Remaining 62492 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_

### L3 Routing

- **Interior gateway protocol → OSPFv2 Area 0 (single area)**  
  One site / one autonomous system with 12 subnets (< 50). A single backbone area keeps every router's LSDB identical and small, so SPF (Dijkstra) runs in milliseconds and link-state flooding gives sub-second convergence after a failure. Multi-area design would add ABR complexity with no scaling benefit at this size; distance-vector protocols (RIP) were rejected for slow, hop-count-limited convergence.  
  _Refs: RFC 2328_

### L2 Switching

- **VLAN segmentation → 802.1Q VLANs [10, 11, 12, 20, 30, 40, 50, 60, 99]**  
  Each traffic class (per-building staff data, voice, corporate Wi-Fi, guest, AP management, servers, network management) gets its own VLAN/broadcast domain so broadcast load is contained and inter-VLAN traffic is forced through the L3 core where ACLs apply. Per-building data VLANs keep broadcast domains under ~500 hosts.  
  _Refs: IEEE 802.1Q_
- **Trunk hardening → Pruned trunks, native VLAN 999, DTP off**  
  Every trunk carries only the VLANs that exist in that building ('switchport trunk allowed vlan <list>', never 'all'), uses unused native VLAN 999 so untagged frames land nowhere (defeats double-tag VLAN hopping), and disables DTP with 'switchport nonegotiate' so a host cannot negotiate a trunk.  
  _Refs: IEEE 802.1Q, Cisco SAFE_
- **Spanning tree → Rapid PVST+ (802.1w), core = root bridge**  
  Redundant uplinks create L2 loops; RSTP's proposal/agreement handshake converges in < 1 s versus 30-50 s for legacy 802.1D. The core is pinned as root (priority 4096) for every VLAN so traffic follows the designed path; edge ports use PortFast + BPDU Guard so a rogue switch is err-disabled instead of moving the root.  
  _Refs: IEEE 802.1w, IEEE 802.1D-2004_
- **Link aggregation → LACP (mode active) for multi-lane uplinks**  
  Uplinks needing > 10 Gb/s are bundled with LACP so STP sees one logical port (no blocked member) and all members carry traffic.  
  _Refs: IEEE 802.1AX_

### Security

- **ACL GUEST-ISOLATION → Extended ACL in on VLAN 40**  
  Applied inbound on the VLAN 40 gateway interface, i.e. it filters traffic sourced from hosts in that VLAN. 4 entries, most specific first, ending in an explicit deny so denied flows are logged. Wildcard masks are computed bitwise from each subnet prefix (wildcard = ~mask & 0xFFFFFFFF).  
  _Refs: Cisco IOS ACL reference_
- **ACL PROTECT-MGMT → Extended ACL out on VLAN 99**  
  Applied outbound on the VLAN 99 gateway interface, i.e. it filters traffic destined to hosts in that VLAN. 7 entries, most specific first, ending in an explicit deny so denied flows are logged. Wildcard masks are computed bitwise from each subnet prefix (wildcard = ~mask & 0xFFFFFFFF).  
  _Refs: Cisco IOS ACL reference_
