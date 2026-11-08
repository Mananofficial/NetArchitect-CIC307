# NetArchitect Design Report - Global WAN - 4 cities + Cloud VPC, 2,000 IoT/scanners

- **Profile:** global_wan
- **Root prefix:** 10.50.0.0/16
- **Topology tier:** Hub-and-spoke WAN with cloud transit at hub
- **Routing:** OSPF multi-area + eBGP AS65050<->AS64512
- **Devices configured:** DEL-RTR1, BOM-RTR1, BLR-RTR1, MAA-RTR1

## Physical media & transceivers

| Link | Distance | Media | Transceiver | Lanes | Loss / Budget (dB) | Attenuator |
|---|---|---|---|---|---|---|
| DEL-BOM-WAN | 1,400.0 km | Carrier WAN circuit (MEF E-Line / Internet) | 1000BASE-LX SFP at carrier NID | 1 | - | - |
| DEL-BLR-WAN | 2,150.0 km | Carrier WAN circuit (MEF E-Line / Internet) | 1000BASE-LX SFP at carrier NID | 1 | - | - |
| DEL-MAA-WAN | 2,200.0 km | Carrier WAN circuit (MEF E-Line / Internet) | 1000BASE-LX SFP at carrier NID | 1 | - | - |

## Site summary blocks

| Site | Block | OSPF area |
|---|---|---|
| DELHI | 10.50.0.0/21 | 0 |
| MUMBAI | 10.50.8.0/21 | 1 |
| BENGALURU | 10.50.16.0/22 | 2 |
| CHENNAI | 10.50.20.0/22 | 3 |

## VLSM allocation

| Name | Site | VLAN | CIDR | Mask | Wildcard | Gateway | Broadcast | Hosts req/usable | Util % |
|---|---|---|---|---|---|---|---|---|---|
| DEL-USERS | DELHI | 10 | 10.50.0.0/23 | 255.255.254.0 | 0.0.1.255 | 10.50.0.1 | 10.50.1.255 | 300/510 | 58.8 |
| DEL-IOT | DELHI | 30 | 10.50.2.0/23 | 255.255.254.0 | 0.0.1.255 | 10.50.2.1 | 10.50.3.255 | 300/510 | 58.8 |
| DEL-SCANNERS | DELHI | 40 | 10.50.4.0/24 | 255.255.255.0 | 0.0.0.255 | 10.50.4.1 | 10.50.4.255 | 150/254 | 59.1 |
| DEL-MGMT | DELHI | 99 | 10.50.5.0/27 | 255.255.255.224 | 0.0.0.31 | 10.50.5.1 | 10.50.5.31 | 20/30 | 66.7 |
| LO-DEL-RTR1 | DELHI | - | 10.50.5.32/32 | 255.255.255.255 | 0.0.0.0 | 10.50.5.32 | - | 1/1 | 100.0 |
| BOM-IOT | MUMBAI | 30 | 10.50.8.0/23 | 255.255.254.0 | 0.0.1.255 | 10.50.8.1 | 10.50.9.255 | 350/510 | 68.6 |
| BOM-USERS | MUMBAI | 10 | 10.50.10.0/24 | 255.255.255.0 | 0.0.0.255 | 10.50.10.1 | 10.50.10.255 | 150/254 | 59.1 |
| BOM-SCANNERS | MUMBAI | 40 | 10.50.11.0/24 | 255.255.255.0 | 0.0.0.255 | 10.50.11.1 | 10.50.11.255 | 150/254 | 59.1 |
| BOM-MGMT | MUMBAI | 99 | 10.50.12.0/27 | 255.255.255.224 | 0.0.0.31 | 10.50.12.1 | 10.50.12.31 | 20/30 | 66.7 |
| DEL-BOM-WAN-P2P | MUMBAI | - | 10.50.12.32/31 | 255.255.255.254 | 0.0.0.1 | 10.50.12.32 | - | 2/2 | 100.0 |
| LO-BOM-RTR1 | MUMBAI | - | 10.50.12.34/32 | 255.255.255.255 | 0.0.0.0 | 10.50.12.34 | - | 1/1 | 100.0 |
| BLR-IOT | BENGALURU | 30 | 10.50.16.0/23 | 255.255.254.0 | 0.0.1.255 | 10.50.16.1 | 10.50.17.255 | 400/510 | 78.4 |
| BLR-SCANNERS | BENGALURU | 40 | 10.50.18.0/24 | 255.255.255.0 | 0.0.0.255 | 10.50.18.1 | 10.50.18.255 | 150/254 | 59.1 |
| BLR-USERS | BENGALURU | 10 | 10.50.19.0/25 | 255.255.255.128 | 0.0.0.127 | 10.50.19.1 | 10.50.19.127 | 120/126 | 95.2 |
| BLR-MGMT | BENGALURU | 99 | 10.50.19.128/27 | 255.255.255.224 | 0.0.0.31 | 10.50.19.129 | 10.50.19.159 | 20/30 | 66.7 |
| DEL-BLR-WAN-P2P | BENGALURU | - | 10.50.19.160/31 | 255.255.255.254 | 0.0.0.1 | 10.50.19.160 | - | 2/2 | 100.0 |
| LO-BLR-RTR1 | BENGALURU | - | 10.50.19.162/32 | 255.255.255.255 | 0.0.0.0 | 10.50.19.162 | - | 1/1 | 100.0 |
| MAA-IOT | CHENNAI | 30 | 10.50.20.0/23 | 255.255.254.0 | 0.0.1.255 | 10.50.20.1 | 10.50.21.255 | 350/510 | 68.6 |
| MAA-SCANNERS | CHENNAI | 40 | 10.50.22.0/24 | 255.255.255.0 | 0.0.0.255 | 10.50.22.1 | 10.50.22.255 | 150/254 | 59.1 |
| MAA-USERS | CHENNAI | 10 | 10.50.23.0/25 | 255.255.255.128 | 0.0.0.127 | 10.50.23.1 | 10.50.23.127 | 80/126 | 63.5 |
| MAA-MGMT | CHENNAI | 99 | 10.50.23.128/27 | 255.255.255.224 | 0.0.0.31 | 10.50.23.129 | 10.50.23.159 | 20/30 | 66.7 |
| DEL-MAA-WAN-P2P | CHENNAI | - | 10.50.23.160/31 | 255.255.255.254 | 0.0.0.1 | 10.50.23.160 | - | 2/2 | 100.0 |
| LO-MAA-RTR1 | CHENNAI | - | 10.50.23.162/32 | 255.255.255.255 | 0.0.0.0 | 10.50.23.162 | - | 1/1 | 100.0 |

## Latency verification

| Link | Path | One-way ms | RTT ms | Budget | OK |
|---|---|---|---|---|---|
| DEL-BOM-WAN | primary | 8.95 | 17.9 | - | yes |
| DEL-BLR-WAN | primary | 13.728 | 27.456 | - | yes |
| DEL-MAA-WAN | primary | 14.046 | 28.092 | - | yes |

## Interface map

| Link | A side | B side | Transit |
|---|---|---|---|
| DEL-BOM-WAN | DEL-RTR1 GigabitEthernet1/0 | BOM-RTR1 GigabitEthernet1/0 | 10.50.12.32/31 |
| DEL-BLR-WAN | DEL-RTR1 GigabitEthernet2/0 | BLR-RTR1 GigabitEthernet1/0 | 10.50.19.160/31 |
| DEL-MAA-WAN | DEL-RTR1 GigabitEthernet3/0 | MAA-RTR1 GigabitEthernet1/0 | 10.50.23.160/31 |

## Architectural rationale log

### Topology

- **Profile 'global_wan' → Hub-and-spoke WAN with cloud transit at hub**  
  4 cities plus a cloud VPC: HQ is the OSPF backbone and the single controlled egress to the cloud (IPsec + eBGP), so security policy is enforced in one place and remote areas only need a path to the hub.  
  _Refs: Cisco SAFE/Campus design guides_

### VLSM

- **Site block BENGALURU → 10.50.16.0/22**  
  Site subnets need 931 addresses in total; rounded up to one power-of-two block (/22, 1024 addresses) so the whole site can be advertised as a single summary route 10.50.16.0/22.  
  _Refs: RFC 4632_
- **Site block CHENNAI → 10.50.20.0/22**  
  Site subnets need 931 addresses in total; rounded up to one power-of-two block (/22, 1024 addresses) so the whole site can be advertised as a single summary route 10.50.20.0/22.  
  _Refs: RFC 4632_
- **Site block DELHI → 10.50.0.0/21**  
  Site subnets need 1313 addresses in total; rounded up to one power-of-two block (/21, 2048 addresses) so the whole site can be advertised as a single summary route 10.50.0.0/21.  
  _Refs: RFC 4632_
- **Site block MUMBAI → 10.50.8.0/21**  
  Site subnets need 1059 addresses in total; rounded up to one power-of-two block (/21, 2048 addresses) so the whole site can be advertised as a single summary route 10.50.8.0/21.  
  _Refs: RFC 4632_
- **DEL-USERS → 10.50.0.0/23**  
  300 hosts + 2 (network, broadcast) = 302 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.50.0.1 (first usable), broadcast 10.50.1.255. Utilization 300/510 = 58.8%.  
  _Refs: RFC 950, RFC 1878_
- **DEL-IOT → 10.50.2.0/23**  
  300 hosts + 2 (network, broadcast) = 302 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.50.2.1 (first usable), broadcast 10.50.3.255. Utilization 300/510 = 58.8%.  
  _Refs: RFC 950, RFC 1878_
- **DEL-SCANNERS → 10.50.4.0/24**  
  150 hosts + 2 (network, broadcast) = 152 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.50.4.1 (first usable), broadcast 10.50.4.255. Utilization 150/254 = 59.1%.  
  _Refs: RFC 950, RFC 1878_
- **DEL-MGMT → 10.50.5.0/27**  
  20 hosts + 2 (network, broadcast) = 22 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.50.5.1 (first usable), broadcast 10.50.5.31. Utilization 20/30 = 66.7%.  
  _Refs: RFC 950, RFC 1878_
- **LO-DEL-RTR1 → 10.50.5.32/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site DELHI 10.50.0.0/21 → 5 subnets, 1313 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 1313 of 2048 addresses consumed (64.1% of the block); host efficiency 771/1305 usable = 59.1%. Remaining 735 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_
- **BOM-IOT → 10.50.8.0/23**  
  350 hosts + 2 (network, broadcast) = 352 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.50.8.1 (first usable), broadcast 10.50.9.255. Utilization 350/510 = 68.6%.  
  _Refs: RFC 950, RFC 1878_
- **BOM-USERS → 10.50.10.0/24**  
  150 hosts + 2 (network, broadcast) = 152 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.50.10.1 (first usable), broadcast 10.50.10.255. Utilization 150/254 = 59.1%.  
  _Refs: RFC 950, RFC 1878_
- **BOM-SCANNERS → 10.50.11.0/24**  
  150 hosts + 2 (network, broadcast) = 152 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.50.11.1 (first usable), broadcast 10.50.11.255. Utilization 150/254 = 59.1%.  
  _Refs: RFC 950, RFC 1878_
- **BOM-MGMT → 10.50.12.0/27**  
  20 hosts + 2 (network, broadcast) = 22 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.50.12.1 (first usable), broadcast 10.50.12.31. Utilization 20/30 = 66.7%.  
  _Refs: RFC 950, RFC 1878_
- **DEL-BOM-WAN-P2P → 10.50.12.32/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-BOM-RTR1 → 10.50.12.34/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site MUMBAI 10.50.8.0/21 → 6 subnets, 1059 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 1059 of 2048 addresses consumed (51.7% of the block); host efficiency 673/1051 usable = 64.0%. Remaining 989 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_
- **BLR-IOT → 10.50.16.0/23**  
  400 hosts + 2 (network, broadcast) = 402 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.50.16.1 (first usable), broadcast 10.50.17.255. Utilization 400/510 = 78.4%.  
  _Refs: RFC 950, RFC 1878_
- **BLR-SCANNERS → 10.50.18.0/24**  
  150 hosts + 2 (network, broadcast) = 152 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.50.18.1 (first usable), broadcast 10.50.18.255. Utilization 150/254 = 59.1%.  
  _Refs: RFC 950, RFC 1878_
- **BLR-USERS → 10.50.19.0/25**  
  120 hosts + 2 (network, broadcast) = 122 addresses; smallest power of two >= that is 2^7 = 128 -> /25 (mask 255.255.255.128, wildcard 0.0.0.127). Gateway 10.50.19.1 (first usable), broadcast 10.50.19.127. Utilization 120/126 = 95.2%.  
  _Refs: RFC 950, RFC 1878_
- **BLR-MGMT → 10.50.19.128/27**  
  20 hosts + 2 (network, broadcast) = 22 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.50.19.129 (first usable), broadcast 10.50.19.159. Utilization 20/30 = 66.7%.  
  _Refs: RFC 950, RFC 1878_
- **DEL-BLR-WAN-P2P → 10.50.19.160/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-BLR-RTR1 → 10.50.19.162/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site BENGALURU 10.50.16.0/22 → 6 subnets, 931 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 931 of 1024 addresses consumed (90.9% of the block); host efficiency 693/923 usable = 75.1%. Remaining 93 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_
- **MAA-IOT → 10.50.20.0/23**  
  350 hosts + 2 (network, broadcast) = 352 addresses; smallest power of two >= that is 2^9 = 512 -> /23 (mask 255.255.254.0, wildcard 0.0.1.255). Gateway 10.50.20.1 (first usable), broadcast 10.50.21.255. Utilization 350/510 = 68.6%.  
  _Refs: RFC 950, RFC 1878_
- **MAA-SCANNERS → 10.50.22.0/24**  
  150 hosts + 2 (network, broadcast) = 152 addresses; smallest power of two >= that is 2^8 = 256 -> /24 (mask 255.255.255.0, wildcard 0.0.0.255). Gateway 10.50.22.1 (first usable), broadcast 10.50.22.255. Utilization 150/254 = 59.1%.  
  _Refs: RFC 950, RFC 1878_
- **MAA-USERS → 10.50.23.0/25**  
  80 hosts + 2 (network, broadcast) = 82 addresses; smallest power of two >= that is 2^7 = 128 -> /25 (mask 255.255.255.128, wildcard 0.0.0.127). Gateway 10.50.23.1 (first usable), broadcast 10.50.23.127. Utilization 80/126 = 63.5%.  
  _Refs: RFC 950, RFC 1878_
- **MAA-MGMT → 10.50.23.128/27**  
  20 hosts + 2 (network, broadcast) = 22 addresses; smallest power of two >= that is 2^5 = 32 -> /27 (mask 255.255.255.224, wildcard 0.0.0.31). Gateway 10.50.23.129 (first usable), broadcast 10.50.23.159. Utilization 20/30 = 66.7%.  
  _Refs: RFC 950, RFC 1878_
- **DEL-MAA-WAN-P2P → 10.50.23.160/31**  
  Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/broadcast needed on a 2-node link), saving 50% vs a /30.  
  _Refs: RFC 3021_
- **LO-MAA-RTR1 → 10.50.23.162/32**  
  Router loopback / router-ID: a /32 host route is stable and always up.  
  _Refs: RFC 2328 s.C.1_
- **site CHENNAI 10.50.20.0/22 → 6 subnets, 931 addresses**  
  Requests were sorted by required block size (largest first) and placed sequentially on their natural bit boundaries, which guarantees zero overlap and no fragmentation. 931 of 1024 addresses consumed (90.9% of the block); host efficiency 603/923 usable = 65.3%. Remaining 93 addresses are contiguous at the top of the block for growth.  
  _Refs: RFC 1878, RFC 4632, RFC 1918_

### L3 Routing

- **Interior gateway protocol → OSPFv2 multi-area**  
  Design spans 4 geographically separate sites. Each remote site gets its own area (DELHI=Area 0, MUMBAI=Area 1, BENGALURU=Area 2, CHENNAI=Area 3) attached to backbone Area 0 at DELHI. This isolates routing domains: a flapping metro/WAN link only triggers SPF inside its own area, while other areas receive a single Type-3 summary LSA from the ABR. Combined with per-site summary blocks this keeps LSDB size and SPF cost bounded as sites grow.  
  _Refs: RFC 2328 s.3, RFC 3101_
- **Route summarization → ABR 'area range' per site block**  
  Hierarchical VLSM gave every site one contiguous power-of-two block, so the ABR advertises exactly one summary per area instead of every VLAN. Summaries hide internal flaps from the rest of the network and shrink every routing table.  
  _Refs: RFC 4632, RFC 2328 s.12.4.3_
- **Cloud boundary (AWS-VPC-MUMBAI) → eBGP AS65050 <-> AS64512 over IPsec**  
  The cloud VPC is a separate administrative/routing domain; OSPF must not extend into a provider's network. eBGP gives policy control (prefix-lists, AS-path) and is what cloud VPN gateways speak natively. Only the enterprise aggregate is advertised (anchored with a Null0 route so it is always in the RIB), and only the VPC CIDR 10.100.0.0/16 is accepted. Private ASNs from RFC 6996 are used.  
  _Refs: RFC 4271, RFC 6996, RFC 4301_

### L1 Media

- **DEL-BOM-WAN → Carrier-leased circuit**  
  At 1400 km no un-amplified 10G single-mode optic closes the power budget (10G-ZR tops out at 80 km), and private dark fiber with DWDM amplification is not cost-justified. A carrier circuit is used, with a short OS2 1000BASE-LX SFP handoff at the carrier NID. Expected one-way delay ~8.918 ms (fiber route x1.3).  
  _Refs: MEF 6.2, ITU-T G.652.D_
- **DEL-BLR-WAN → Carrier-leased circuit**  
  At 2150 km no un-amplified 10G single-mode optic closes the power budget (10G-ZR tops out at 80 km), and private dark fiber with DWDM amplification is not cost-justified. A carrier circuit is used, with a short OS2 1000BASE-LX SFP handoff at the carrier NID. Expected one-way delay ~13.696 ms (fiber route x1.3).  
  _Refs: MEF 6.2, ITU-T G.652.D_
- **DEL-MAA-WAN → Carrier-leased circuit**  
  At 2200 km no un-amplified 10G single-mode optic closes the power budget (10G-ZR tops out at 80 km), and private dark fiber with DWDM amplification is not cost-justified. A carrier circuit is used, with a short OS2 1000BASE-LX SFP handoff at the carrier NID. Expected one-way delay ~14.014 ms (fiber route x1.3).  
  _Refs: MEF 6.2, ITU-T G.652.D_

### Security

- **Cloud VPN → IKEv2 + IPsec VTI (AES-256, SHA-256, DH14, PFS)**  
  Traffic to AWS-VPC-MUMBAI crosses the public Internet, so it is encrypted in an IPsec tunnel. A route-based VTI (instead of a crypto-map) lets eBGP run over the tunnel and fail over dynamically. TCP MSS is clamped to 1379 bytes so ESP + outer-IP tunnel overhead never fragments 1500-byte packets.  
  _Refs: RFC 7296, RFC 4301, RFC 4303_
- **ACL IOT-SEGMENT → Extended ACL in on VLAN 30**  
  Applied inbound on the VLAN 30 gateway interface, i.e. it filters traffic sourced from hosts in that VLAN. 6 entries, most specific first, ending in an explicit deny so denied flows are logged. Wildcard masks are computed bitwise from each subnet prefix (wildcard = ~mask & 0xFFFFFFFF).  
  _Refs: Cisco IOS ACL reference_
