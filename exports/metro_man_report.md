# NetArchitect Design Report - Metro MAN - HQ + 2 remote sites + FinTech colo

- **Profile:** metro_man
- **Root prefix:** 10.20.0.0/16
- **Topology tier:** Dual-homed hub-and-spoke MAN
- **Routing:** OSPF multi-area
- **Devices configured:** HQ-RTR1, REMA-RTR1, REMB-RTR1, COLO-RTR1

## Physical media & transceivers

| Link | Distance | Media | Transceiver | Lanes | Loss / Budget (dB) | Attenuator |
|---|---|---|---|---|---|---|
| HQ-REMA-PRIMARY | 15.0 km | OS2 SMF (9/125 um) | 10GBASE-ER SFP+ | 1 | 4.95 / 11.1 | 2 dB |
| HQ-REMA-SECONDARY | 18.0 km | Carrier EVPL (MEF E-Line) | 1000BASE-LX SFP to carrier NID | 1 | - | - |
| HQ-REMB-PRIMARY | 35.0 km | OS2 SMF (9/125 um) | 10G-ZR SFP+ | 1 | 10.35 / 24.0 | 2 dB |
| HQ-REMB-SECONDARY | 38.0 km | Carrier EVPL (MEF E-Line) | 1000BASE-LX SFP to carrier NID | 1 | - | - |
| HQ-COLO-PRIMARY | 22.0 km | OS2 SMF (9/125 um) | 10GBASE-ER SFP+ | 1 | 6.9 / 11.1 | - |
| HQ-COLO-SECONDARY | 25.0 km | Carrier EVPL (MEF E-Line) | 10GBASE-LR SFP+ to carrier NID | 1 | - | - |

## Site summary blocks

| Site | Block | OSPF area |
|---|---|---|
| HQ | 10.20.0.0/23 | 0 |
| REMOTE-A | 10.20.2.0/24 | 1 |
| REMOTE-B | 10.20.3.0/24 | 2 |
| COLO | 10.20.4.0/26 | 0 |

## VLSM allocation

| Name | Site | VLAN | CIDR | Mask | Wildcard | Gateway | Broadcast | Hosts req/usable | Util % |
|---|---|---|---|---|---|---|---|---|---|
| HQ-USERS | HQ | 10 | 10.20.0.0/24 | 255.255.255.0 | 0.0.0.255 | 10.20.0.1 | 10.20.0.255 | 200/254 | 78.7 |
| HQ-VOICE | HQ | 20 | 10.20.1.0/25 | 255.255.255.128 | 0.0.0.127 | 10.20.1.1 | 10.20.1.127 | 120/126 | 95.2 |
| HQ-SERVERS | HQ | 30 | 10.20.1.128/27 | 255.255.255.224 | 0.0.0.31 | 10.20.1.129 | 10.20.1.159 | 30/30 | 100.0 |
| HQ-MGMT | HQ | 99 | 10.20.1.160/27 | 255.255.255.224 | 0.0.0.31 | 10.20.1.161 | 10.20.1.191 | 20/30 | 66.7 |
| LO-HQ-RTR1 | HQ | - | 10.20.1.192/32 | 255.255.255.255 | 0.0.0.0 | 10.20.1.192 | - | 1/1 | 100.0 |
| REMA-USERS | REMOTE-A | 10 | 10.20.2.0/25 | 255.255.255.128 | 0.0.0.127 | 10.20.2.1 | 10.20.2.127 | 100/126 | 79.4 |
| REMA-VOICE | REMOTE-A | 20 | 10.20.2.128/26 | 255.255.255.192 | 0.0.0.63 | 10.20.2.129 | 10.20.2.191 | 60/62 | 96.8 |
| REMA-MGMT | REMOTE-A | 99 | 10.20.2.192/28 | 255.255.255.240 | 0.0.0.15 | 10.20.2.193 | 10.20.2.207 | 10/14 | 71.4 |
| HQ-REMA-PRIMARY-P2P | REMOTE-A | - | 10.20.2.208/31 | 255.255.255.254 | 0.0.0.1 | 10.20.2.208 | - | 2/2 | 100.0 |
| HQ-REMA-SECONDARY-P2P | REMOTE-A | - | 10.20.2.210/31 | 255.255.255.254 | 0.0.0.1 | 10.20.2.210 | - | 2/2 | 100.0 |
| LO-REMA-RTR1 | REMOTE-A | - | 10.20.2.212/32 | 255.255.255.255 | 0.0.0.0 | 10.20.2.212 | - | 1/1 | 100.0 |
| REMB-USERS | REMOTE-B | 10 | 10.20.3.0/25 | 255.255.255.128 | 0.0.0.127 | 10.20.3.1 | 10.20.3.127 | 70/126 | 55.6 |
| REMB-VOICE | REMOTE-B | 20 | 10.20.3.128/26 | 255.255.255.192 | 0.0.0.63 | 10.20.3.129 | 10.20.3.191 | 40/62 | 64.5 |
| REMB-MGMT | REMOTE-B | 99 | 10.20.3.192/28 | 255.255.255.240 | 0.0.0.15 | 10.20.3.193 | 10.20.3.207 | 10/14 | 71.4 |
| HQ-REMB-PRIMARY-P2P | REMOTE-B | - | 10.20.3.208/31 | 255.255.255.254 | 0.0.0.1 | 10.20.3.208 | - | 2/2 | 100.0 |
| HQ-REMB-SECONDARY-P2P | REMOTE-B | - | 10.20.3.210/31 | 255.255.255.254 | 0.0.0.1 | 10.20.3.210 | - | 2/2 | 100.0 |
| LO-REMB-RTR1 | REMOTE-B | - | 10.20.3.212/32 | 255.255.255.255 | 0.0.0.0 | 10.20.3.212 | - | 1/1 | 100.0 |
| COLO-TRADING | COLO | 40 | 10.20.4.0/27 | 255.255.255.224 | 0.0.0.31 | 10.20.4.1 | 10.20.4.31 | 30/30 | 100.0 |
| COLO-MGMT | COLO | 99 | 10.20.4.32/28 | 255.255.255.240 | 0.0.0.15 | 10.20.4.33 | 10.20.4.47 | 10/14 | 71.4 |
| HQ-COLO-PRIMARY-P2P | COLO | - | 10.20.4.48/31 | 255.255.255.254 | 0.0.0.1 | 10.20.4.48 | - | 2/2 | 100.0 |
| HQ-COLO-SECONDARY-P2P | COLO | - | 10.20.4.50/31 | 255.255.255.254 | 0.0.0.1 | 10.20.4.50 | - | 2/2 | 100.0 |
| LO-COLO-RTR1 | COLO | - | 10.20.4.52/32 | 255.255.255.255 | 0.0.0.0 | 10.20.4.52 | - | 1/1 | 100.0 |

## Latency verification

| Link | Path | One-way ms | RTT ms | Budget | OK |
|---|---|---|---|---|---|
| HQ-REMA-PRIMARY | primary | 0.0947 | 0.189 | 5.0 | yes |
| HQ-REMA-SECONDARY | secondary | 0.6202 | 1.24 | 5.0 | yes |
| HQ-REMB-PRIMARY | primary | 0.1927 | 0.385 | 5.0 | yes |
| HQ-REMB-SECONDARY | secondary | 0.7182 | 1.436 | 5.0 | yes |
| HQ-COLO-PRIMARY | primary | 0.129 | 0.258 | 5.0 | yes |
| HQ-COLO-SECONDARY | secondary | 0.6437 | 1.287 | 5.0 | yes |

## Interface map

| Link | A side | B side | Transit |
|---|---|---|---|
| HQ-REMA-PRIMARY | HQ-RTR1 GigabitEthernet1/0 | REMA-RTR1 GigabitEthernet1/0 | 10.20.2.208/31 |
| HQ-REMA-SECONDARY | HQ-RTR1 GigabitEthernet2/0 | REMA-RTR1 GigabitEthernet2/0 | 10.20.2.210/31 |
| HQ-REMB-PRIMARY | HQ-RTR1 GigabitEthernet3/0 | REMB-RTR1 GigabitEthernet1/0 | 10.20.3.208/31 |
| HQ-REMB-SECONDARY | HQ-RTR1 GigabitEthernet4/0 | REMB-RTR1 GigabitEthernet2/0 | 10.20.3.210/31 |
| HQ-COLO-PRIMARY | HQ-RTR1 GigabitEthernet5/0 | COLO-RTR1 GigabitEthernet1/0 | 10.20.4.48/31 |
| HQ-COLO-SECONDARY | HQ-RTR1 GigabitEthernet6/0 | COLO-RTR1 GigabitEthernet2/0 | 10.20.4.50/31 |

## Architectural rationale log

### Topology

- **Profile 'metro_man' → Dual-homed hub-and-spoke MAN**  
  4 metro sites: each remote site is dual-homed to the HQ hub over two physically diverse paths (primary dark fiber, secondary carrier EVPL) so a single fiber cut never isolates a site.  
  _Refs: Cisco SAFE/Campus design guides_

### VLSM

- **Site block COLO → 10.20.4.0/26**  
  Site subnets need 53 addresses in total; rounded up to one power-of-two block (/26, 64 addresses) so the whole site can be advertised as a single summary route 10.20.4.0/26.  
  _Refs: RFC 4632_
- **Site block HQ → 10.20.0.0/23**  
  Site subnets need 449 addresses in total; rounded up to one power-of-two block (/23, 512 addresses) so the whole site can be advertised as a single summary route 10.20.0.0/23.  
  _Refs: RFC 4632_
- **Site block REMOTE-A → 10.20.2.0/24**  
  Site subnets need 213 addresses in total; rounded up to one power-of-two block (/24, 256 addresses) so the whole site can be advertised as a single summary route 10.20.2.0/24.  
  _Refs: RFC 4632_
- **Site block REMOTE-B → 10.20.3.0/24**  
  Site subnets need 213 addresses in total; rounded up to one power-of-two block (/24, 256 addresses) so the whole site can be advertised as a single summary route 10.20.3.0/24.  
  _Refs: RFC 4632_
- **HQ-USERS → 10.20.0.0/24**  
  200 hosts + 2 (network, broadcast) = 202 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.20.0.1 (first usable), broadcast 10.20.0.255. Utilization 200/254 = 78.7%.  
  _Refs: RFC 950, RFC 1878_
- **HQ-VOICE → 10.20.1.0/25**  
  120 hosts + 2 (network, broadcast) = 122 addresses; smallest power of two >= that is 2^7 = 128 -> /25 (mask 255.255.255.128, wildcard 0.0.0.127). Gateway 10.20.1.1 (first usable), broadcast 10.20.1.127. Utilization 120/126 = 95.2%.  
  _Refs: RFC 950, RFC 1878_
- **HQ-SERVERS → 10.20.1.128/27**  
  30 hosts + 2 (network, broadcast) = 32 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.20.1.129 (first usable), broadcast 10.20.1.159. Utilization 30/30 = 100.0%.  
  _Refs: RFC 950, RFC 1878_
- **HQ-MGMT → 10.20.1.160/27**  
  20 hosts + 2 (network, broadcast) = 22 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.20.1.161 (first usable), broadcast 10.20.1.191. Utilization 20/30 = 66.7%.  
  _Refs: RFC 950, RFC 1878_
- **LO-HQ-RTR1 → 10.20.1.192/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site HQ 10.20.0.0/23 → 5 subnets, 449 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 449 of 512 addresses consumed (87.7% of the block); host efficiency 371/441 usable = 84.1%. Remaining 63 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_
- **REMA-USERS → 10.20.2.0/25**  
  100 hosts + 2 (network, broadcast) = 102 addresses; smallest power of two >= that is 2^7 = 128 -> /25 (mask 255.255.255.128, wildcard 0.0.0.127). Gateway 10.20.2.1 (first usable), broadcast 10.20.2.127. Utilization 100/126 = 79.4%.  
  _Refs: RFC 950, RFC 1878_
- **REMA-VOICE → 10.20.2.128/26**  
  60 hosts + 2 (network, broadcast) = 62 addresses; smallest power of two >= that is 2^6 = 64 -> /26 (mask 255.255.255.192, wildcard 0.0.0.63). Gateway 10.20.2.129 (first usable), broadcast 10.20.2.191. Utilization 60/62 = 96.8%.  
  _Refs: RFC 950, RFC 1878_
- **REMA-MGMT → 10.20.2.192/28**  
  10 hosts + 2 (network, broadcast) = 12 addresses; smallest power of two >= that is 2^4 = 16 -> /28 (mask 255.255.255.240, wildcard 0.0.0.15). Gateway 10.20.2.193 (first usable), broadcast 10.20.2.207. Utilization 10/14 = 71.4%.  
  _Refs: RFC 950, RFC 1878_
- **HQ-REMA-PRIMARY-P2P → 10.20.2.208/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **HQ-REMA-SECONDARY-P2P → 10.20.2.210/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-REMA-RTR1 → 10.20.2.212/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site REMOTE-A 10.20.2.0/24 → 6 subnets, 213 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 213 of 256 addresses consumed (83.2% of the block); host efficiency 175/207 usable = 84.5%. Remaining 43 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_
- **REMB-USERS → 10.20.3.0/25**  
  70 hosts + 2 (network, broadcast) = 72 addresses; smallest power of two >= that is 2^7 = 128 -> /25 (mask 255.255.255.128, wildcard 0.0.0.127). Gateway 10.20.3.1 (first usable), broadcast 10.20.3.127. Utilization 70/126 = 55.6%.  
  _Refs: RFC 950, RFC 1878_
- **REMB-VOICE → 10.20.3.128/26**  
  40 hosts + 2 (network, broadcast) = 42 addresses; smallest power of two >= that is 2^6 = 64 -> /26 (mask 255.255.255.192, wildcard 0.0.0.63). Gateway 10.20.3.129 (first usable), broadcast 10.20.3.191. Utilization 40/62 = 64.5%.  
  _Refs: RFC 950, RFC 1878_
- **REMB-MGMT → 10.20.3.192/28**  
  10 hosts + 2 (network, broadcast) = 12 addresses; smallest power of two >= that is 2^4 = 16 -> /28 (mask 255.255.255.240, wildcard 0.0.0.15). Gateway 10.20.3.193 (first usable), broadcast 10.20.3.207. Utilization 10/14 = 71.4%.  
  _Refs: RFC 950, RFC 1878_
- **HQ-REMB-PRIMARY-P2P → 10.20.3.208/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **HQ-REMB-SECONDARY-P2P → 10.20.3.210/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-REMB-RTR1 → 10.20.3.212/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site REMOTE-B 10.20.3.0/24 → 6 subnets, 213 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 213 of 256 addresses consumed (83.2% of the block); host efficiency 125/207 usable = 60.4%. Remaining 43 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_
- **COLO-TRADING → 10.20.4.0/27**  
  30 hosts + 2 (network, broadcast) = 32 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.20.4.1 (first usable), broadcast 10.20.4.31. Utilization 30/30 = 100.0%.  
  _Refs: RFC 950, RFC 1878_
- **COLO-MGMT → 10.20.4.32/28**  
  10 hosts + 2 (network, broadcast) = 12 addresses; smallest power of two >= that is 2^4 = 16 -> /28 (mask 255.255.255.240, wildcard 0.0.0.15). Gateway 10.20.4.33 (first usable), broadcast 10.20.4.47. Utilization 10/14 = 71.4%.  
  _Refs: RFC 950, RFC 1878_
- **HQ-COLO-PRIMARY-P2P → 10.20.4.48/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **HQ-COLO-SECONDARY-P2P → 10.20.4.50/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-COLO-RTR1 → 10.20.4.52/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site COLO 10.20.4.0/26 → 5 subnets, 53 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 53 of 64 addresses consumed (82.8% of the block); host efficiency 45/49 usable = 91.8%. Remaining 11 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_

### L3 Routing

- **Interior gateway protocol → OSPFv2 multi-area**  
  Design spans 4 geographically separate sites. Each remote site gets its own area (HQ=Area 0, REMOTE-A=Area 1, REMOTE-B=Area 2, COLO=Area 0) attached to backbone Area 0 at HQ. This isolates routing domains: a flapping metro/WAN link only triggers SPF inside its own area, while other areas receive a single Type-3 summary LSA from the ABR. Combined with per-site summary blocks this keeps LSDB size and SPF cost bounded as sites grow.  
  _Refs: RFC 2328 s.3, RFC 3101_
- **Route summarization → ABR 'area range' per site block**  
  Hierarchical VLSM gave every site one contiguous power-of-two block, so the ABR advertises exactly one summary per area instead of every VLAN. Summaries hide internal flaps from the rest of the network and shrink every routing table.  
  _Refs: RFC 4632, RFC 2328 s.12.4.3_
- **Failure detection → BFD 300 ms x 3 on WAN/MAN links**  
  Resiliency is 'dual-homed': OSPF's default dead interval (40 s) is far too slow for a FinTech/latency-sensitive network. BFD detects a dead path in <= 900 ms and tells OSPF to reconverge onto the secondary path immediately.  
  _Refs: RFC 5880, RFC 5882_

### L1 Media

- **HQ-REMA-PRIMARY → OS2 SMF / 10GBASE-ER**  
  Selected OS2 Single-Mode Fiber because link distance (15 km) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber. Optical budget for 10GBASE-ER @1550 nm: Tx(min) -4.7 dBm - Rx sensitivity -15.8 dBm = 11.1 dB. Plant loss = 15 km x 0.25 dB/km + 2 connectors x 0.5 dB + splices = 4.95 dB, leaving 6.15 dB (>= 3.0 dB required margin). Receiver overload check: Tx(max) 4.0 dBm - 4.95 dB = -0.95 dBm exceeds the -1.0 dBm overload point, so a 2 dB inline attenuator is required.  
  _Refs: IEEE 802.3ae cl.52, ITU-T G.652.D, TIA-568.3-D_
- **HQ-REMA-SECONDARY → Carrier EVPL handoff (1000BASE-LX SFP)**  
  This path is a carrier EVPL (Ethernet Virtual Private Line, MEF E-Line) over 18 km of provider fiber, chosen as the physically diverse secondary path so a single dark-fiber cut cannot isolate the site. The provider owns the optical budget; the enterprise only needs a short single-mode 1000BASE-LX SFP handoff to the carrier NID. EVPL is VLAN-aware, so the service can carry 802.1Q-tagged traffic. Estimated one-way latency 0.5882 ms (0.0882 ms propagation + 0.5 ms carrier switching).  
  _Refs: MEF 6.2, MEF 10.4, IEEE 802.1Q_
- **HQ-REMB-PRIMARY → Rejected 10GBASE-ER**  
  10GBASE-ER reach (40 km) covers 35 km, but loss 10.35 dB + 3.0 dB safety margin = 13.35 dB exceeds its 11.1 dB power budget.  
  _Refs: IEEE 802.3ae cl.52_
- **HQ-REMB-PRIMARY → OS2 SMF / 10G-ZR**  
  Selected OS2 Single-Mode Fiber because link distance (35 km) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber. Optical budget for 10G-ZR @1550 nm: Tx(min) 0.0 dBm - Rx sensitivity -24.0 dBm = 24.0 dB. Plant loss = 35 km x 0.25 dB/km + 2 connectors x 0.5 dB + splices = 10.35 dB, leaving 13.65 dB (>= 3.0 dB required margin). Receiver overload check: Tx(max) 4.0 dBm - 10.35 dB = -6.35 dBm exceeds the -7.0 dBm overload point, so a 2 dB inline attenuator is required.  
  _Refs: SFF MSA (non-IEEE), ITU-T G.652.D, TIA-568.3-D_
- **HQ-REMB-SECONDARY → Carrier EVPL handoff (1000BASE-LX SFP)**  
  This path is a carrier EVPL (Ethernet Virtual Private Line, MEF E-Line) over 38 km of provider fiber, chosen as the physically diverse secondary path so a single dark-fiber cut cannot isolate the site. The provider owns the optical budget; the enterprise only needs a short single-mode 1000BASE-LX SFP handoff to the carrier NID. EVPL is VLAN-aware, so the service can carry 802.1Q-tagged traffic. Estimated one-way latency 0.6862 ms (0.1862 ms propagation + 0.5 ms carrier switching).  
  _Refs: MEF 6.2, MEF 10.4, IEEE 802.1Q_
- **HQ-COLO-PRIMARY → OS2 SMF / 10GBASE-ER**  
  Selected OS2 Single-Mode Fiber because link distance (22 km) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber. Optical budget for 10GBASE-ER @1550 nm: Tx(min) -4.7 dBm - Rx sensitivity -15.8 dBm = 11.1 dB. Plant loss = 22 km x 0.25 dB/km + 2 connectors x 0.5 dB + splices = 6.9 dB, leaving 4.20 dB (>= 3.0 dB required margin).  
  _Refs: IEEE 802.3ae cl.52, ITU-T G.652.D, TIA-568.3-D_
- **HQ-COLO-SECONDARY → Carrier EVPL handoff (10GBASE-LR SFP+)**  
  This path is a carrier EVPL (Ethernet Virtual Private Line, MEF E-Line) over 25 km of provider fiber, chosen as the physically diverse secondary path so a single dark-fiber cut cannot isolate the site. The provider owns the optical budget; the enterprise only needs a short single-mode 10GBASE-LR SFP+ handoff to the carrier NID. EVPL is VLAN-aware, so the service can carry 802.1Q-tagged traffic. Estimated one-way latency 0.6225 ms (0.1225 ms propagation + 0.5 ms carrier switching).  
  _Refs: MEF 6.2, MEF 10.4, IEEE 802.1Q_

### Latency

- **HQ-REMA-PRIMARY → RTT 0.189 ms <= 5.0 ms**  
  One-way = propagation/carrier 0.0735 ms + 2 x 0.01 ms forwarding + 0.0012 ms serialization of a 1500-byte frame at 10 Gb/s = 0.0947 ms; RTT = 0.189 ms. Within the sub-5 ms budget on this primary path.  
  _Refs: ITU-T G.114 (delay planning)_
- **HQ-REMA-SECONDARY → RTT 1.24 ms <= 5.0 ms**  
  One-way = propagation/carrier 0.5882 ms + 2 x 0.01 ms forwarding + 0.0120 ms serialization of a 1500-byte frame at 1 Gb/s = 0.6202 ms; RTT = 1.24 ms. Within the sub-5 ms budget on this secondary path.  
  _Refs: ITU-T G.114 (delay planning)_
- **HQ-REMB-PRIMARY → RTT 0.385 ms <= 5.0 ms**  
  One-way = propagation/carrier 0.1715 ms + 2 x 0.01 ms forwarding + 0.0012 ms serialization of a 1500-byte frame at 10 Gb/s = 0.1927 ms; RTT = 0.385 ms. Within the sub-5 ms budget on this primary path.  
  _Refs: ITU-T G.114 (delay planning)_
- **HQ-REMB-SECONDARY → RTT 1.436 ms <= 5.0 ms**  
  One-way = propagation/carrier 0.6862 ms + 2 x 0.01 ms forwarding + 0.0120 ms serialization of a 1500-byte frame at 1 Gb/s = 0.7182 ms; RTT = 1.436 ms. Within the sub-5 ms budget on this secondary path.  
  _Refs: ITU-T G.114 (delay planning)_
- **HQ-COLO-PRIMARY → RTT 0.258 ms <= 5.0 ms**  
  One-way = propagation/carrier 0.1078 ms + 2 x 0.01 ms forwarding + 0.0012 ms serialization of a 1500-byte frame at 10 Gb/s = 0.1290 ms; RTT = 0.258 ms. Within the sub-5 ms budget on this primary path.  
  _Refs: ITU-T G.114 (delay planning)_
- **HQ-COLO-SECONDARY → RTT 1.287 ms <= 5.0 ms**  
  One-way = propagation/carrier 0.6225 ms + 2 x 0.01 ms forwarding + 0.0012 ms serialization of a 1500-byte frame at 10 Gb/s = 0.6437 ms; RTT = 1.287 ms. Within the sub-5 ms budget on this secondary path.  
  _Refs: ITU-T G.114 (delay planning)_

### Resiliency

- **Dual-homed failover → Primary cost 10 / secondary cost 100**  
  Every remote site has two physically diverse paths. Explicit OSPF costs make the dark-fiber path primary; the EVPL path stays in the LSDB as a hot standby. When BFD declares the primary down, SPF selects the secondary with no manual action.  
  _Refs: RFC 2328, RFC 5880_

### QoS

- **Metro QoS policy → LLQ: EF priority 20%, AF41 40%, fair-queue rest**  
  Voice (DSCP EF) gets a strict-priority queue capped at 20% so jitter stays low without starving other classes; FinTech trading flows (DSCP AF41 or any flow to the colo trading subnet) get a 40% bandwidth guarantee; everything else uses fair-queueing. Applied outbound on every metro interface because congestion happens at egress.  
  _Refs: RFC 4594, RFC 3246, RFC 2597_

### Security

- **ACL COLO-PROTECT → Extended ACL out on VLAN 40**  
  Applied outbound on the VLAN 40 gateway interface, i.e. it filters traffic destined to hosts in that VLAN. 7 entries, most specific first, ending in an explicit deny so denied flows are logged. Wildcard masks are computed bitwise from each subnet prefix (wildcard = ~mask & 0xFFFFFFFF).  
  _Refs: Cisco IOS ACL reference_
