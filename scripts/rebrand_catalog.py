"""One-off: give the catalogue real-brand product names and Unsplash photos, consistently across every data file.

Rewrites product names/brands in products.csv, products/*.md, conversations.json, support_tickets.csv and
reviews.csv (old name -> new name, by product_id), and adds an `image_url` column to products.csv.
Photos are free-licence Unsplash photos (https://unsplash.com/license), hot-linked from images.unsplash.com.
Run from the repo root:  python scripts/rebrand_catalog.py
"""
import json
import re
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# subcategory -> (brand, model) options; colour (and a storage/size variant if needed) keeps names unique
MODELS = {
    "Foldable": [("Samsung", "Galaxy Z Fold5 5G"), ("Samsung", "Galaxy Z Flip5 5G"), ("Motorola", "razr 40 Ultra"), ("OnePlus", "Open 5G"), ("Vivo", "X Fold3 Pro")],
    "Mid-range": [("OnePlus", "Nord CE4 5G"), ("Samsung", "Galaxy A55 5G"), ("Nothing", "Phone (2a)"), ("Motorola", "Edge 50 Fusion"), ("Realme", "12 Pro+ 5G"), ("iQOO", "Z9 5G")],
    "Flagship": [("Apple", "iPhone 15 Pro"), ("Samsung", "Galaxy S24 Ultra 5G"), ("Google", "Pixel 8 Pro"), ("OnePlus", "12 5G"), ("Xiaomi", "14 Ultra")],
    "Camera Phone": [("Vivo", "X100 Pro 5G"), ("Google", "Pixel 8"), ("OPPO", "Find X7 Ultra"), ("Xiaomi", "14 Civi"), ("Honor", "Magic6 Pro")],
    "Budget": [("Redmi", "13C 5G"), ("Samsung", "Galaxy M15 5G"), ("Realme", "Narzo N65 5G"), ("POCO", "M6 Pro 5G"), ("Lava", "Blaze Curve 5G")],
    "Creator Laptop": [("Apple", "MacBook Pro 14 M3 Pro"), ("ASUS", "ProArt Studiobook 16 OLED"), ("Dell", "XPS 15 9530"), ("MSI", "Creator Z17 HX")],
    "Ultrabook": [("Apple", "MacBook Air 13 M3"), ("HP", "Spectre x360 14"), ("Dell", "XPS 13 Plus"), ("ASUS", "Zenbook 14 OLED"), ("Lenovo", "Yoga Slim 7i")],
    "Gaming Laptop": [("ASUS", "ROG Strix G16"), ("Lenovo", "Legion Pro 5i"), ("HP", "Omen 16"), ("Acer", "Predator Helios Neo 16"), ("MSI", "Katana 15")],
    "Student Laptop": [("Acer", "Aspire Lite 15"), ("HP", "15s Ryzen 5"), ("Lenovo", "IdeaPad Slim 3"), ("ASUS", "Vivobook 15"), ("Dell", "Inspiron 3520")],
    "Business Laptop": [("Lenovo", "ThinkPad E14 Gen 5"), ("Dell", "Latitude 5440"), ("HP", "EliteBook 840 G10"), ("ASUS", "ExpertBook B5")],
    "Over-ear ANC": [("Sony", "WH-1000XM5"), ("Bose", "QuietComfort Ultra Headphones"), ("Sennheiser", "Momentum 4 Wireless"), ("Apple", "AirPods Max"), ("JBL", "Tour One M2")],
    "On-ear Wireless": [("JBL", "Tune 520BT"), ("Sony", "WH-CH520"), ("boAt", "Rockerz 450"), ("Skullcandy", "Riff Wireless 2")],
    "Gaming Headset": [("HyperX", "Cloud II"), ("Logitech G", "Pro X Gaming Headset"), ("Razer", "BlackShark V2 X"), ("SteelSeries", "Arctis Nova 1")],
    "Over-ear Wired": [("Audio-Technica", "ATH-M50x"), ("Sony", "MDR-7506"), ("Sennheiser", "HD 560S"), ("AKG", "K92")],
    "Neckband": [("boAt", "Rockerz 255 Pro+"), ("OnePlus", "Bullets Wireless Z2"), ("JBL", "Tune 215BT"), ("Realme", "Buds Wireless 3")],
    "Sports Earbuds": [("JBL", "Endurance Peak 3"), ("Beats", "Powerbeats Pro"), ("Jabra", "Elite 8 Active"), ("boAt", "Airdopes 141")],
    "True Wireless": [("Samsung", "Galaxy Buds2 Pro"), ("OnePlus", "Buds 3"), ("Nothing", "Ear (2)"), ("JBL", "Wave Beam"), ("boAt", "Airdopes 311 Pro")],
    "ANC Earbuds": [("Apple", "AirPods Pro (2nd Gen)"), ("Sony", "WF-1000XM5"), ("Bose", "QuietComfort Ultra Earbuds"), ("Sennheiser", "Momentum True Wireless 4")],
    "Wired Earphones": [("Sony", "MDR-EX15AP"), ("JBL", "C100SI"), ("boAt", "BassHeads 100"), ("Apple", "EarPods (USB-C)")],
    "Desktop Speakers": [("Logitech", "Z313 2.1"), ("Creative", "Pebble V3"), ("Edifier", "R1280DB"), ("Zebronics", "Zeb-Fame 2.1")],
    "Soundbar": [("Sony", "HT-S20R 5.1"), ("JBL", "Bar 5.1 Surround"), ("Samsung", "HW-B450 2.1"), ("boAt", "Aavante Bar 1700D")],
    "Party Speaker": [("JBL", "PartyBox 110"), ("Sony", "SRS-XV500"), ("boAt", "PartyPal 300"), ("Zebronics", "Zeb-Thump Pro")],
    "Bluetooth Speaker": [("JBL", "Flip 6"), ("Sony", "SRS-XB13"), ("Bose", "SoundLink Flex"), ("boAt", "Stone 1200"), ("Marshall", "Emberton II")],
    "Smart Speaker": [("Amazon", "Echo Dot (5th Gen)"), ("Google", "Nest Mini (2nd Gen)"), ("Apple", "HomePod mini"), ("Amazon", "Echo Pop")],
    "Fitness Band": [("Xiaomi", "Smart Band 8"), ("Fitbit", "Inspire 3"), ("Samsung", "Galaxy Fit3"), ("HUAWEI", "Band 9")],
    "Kids Watch": [("Noise", "Explorer Kids Smartwatch"), ("boAt", "Wanderer Kids"), ("Fire-Boltt", "Junior"), ("Garmin", "Bounce")],
    "Sports Watch": [("Garmin", "Forerunner 265"), ("Amazfit", "T-Rex 2"), ("COROS", "Pace 3"), ("Polar", "Pacer Pro")],
    "Smartwatch": [("Apple", "Watch Series 9 GPS 45mm"), ("Samsung", "Galaxy Watch6 44mm"), ("Noise", "ColorFit Pro 5"), ("Amazfit", "GTR 4"), ("Fire-Boltt", "Phoenix Ultra")],
    "Pro Tablet": [("Apple", "iPad Pro 11 M2"), ("Samsung", "Galaxy Tab S9 FE"), ("Xiaomi", "Pad 6"), ("Lenovo", "Tab P12")],
    "Kids Tablet": [("Amazon", "Fire HD 8 Kids"), ("Lenovo", "Tab M8 Kids"), ("Samsung", "Galaxy Tab A9 Kids"), ("Honor", "Pad X8 Kids")],
    "Android Tablet": [("Samsung", "Galaxy Tab A9+"), ("Redmi", "Pad SE"), ("Lenovo", "Tab M10 Plus"), ("OnePlus", "Pad Go"), ("Realme", "Pad 2")],
    "Drawing Tablet": [("Wacom", "One by Wacom"), ("XP-Pen", "Deco 01 V2"), ("Huion", "Inspiroy H640P"), ("Wacom", "Intuos Small")],
    "Vlogging Camera": [("Sony", "ZV-1F"), ("Canon", "PowerShot V10"), ("DJI", "Osmo Pocket 3"), ("Sony", "ZV-E10")],
    "Security Camera": [("TP-Link", "Tapo C200"), ("Xiaomi", "360 Home Security Camera 2K"), ("Qubo", "Smart Cam 360"), ("CP Plus", "EZ-P21")],
    "Mirrorless": [("Sony", "Alpha a6400"), ("Canon", "EOS R50"), ("Nikon", "Z50"), ("Fujifilm", "X-T30 II")],
    "Instant Camera": [("Fujifilm", "Instax Mini 12"), ("Polaroid", "Now Gen 2"), ("Fujifilm", "Instax Square SQ1"), ("Kodak", "Smile+")],
    "Action Camera": [("GoPro", "HERO12 Black"), ("DJI", "Osmo Action 4"), ("Insta360", "Ace Pro"), ("GoPro", "HERO11 Black Mini")],
    "Gaming Keyboard": [("Logitech G", "G213 Prodigy"), ("Razer", "Ornata V3"), ("HyperX", "Alloy Origins"), ("Redragon", "K552 Kumara")],
    "Compact 60%": [("Ant Esports", "MK1400 Pro"), ("Royal Kludge", "RK61"), ("Keychron", "K12"), ("Cosmic Byte", "CB-GK-26")],
    "Wireless": [("Logitech", "K380 Multi-Device"), ("Logitech", "MX Keys S"), ("Apple", "Magic Keyboard"), ("HP", "230 Wireless")],
    "Mechanical": [("Keychron", "K2 V2"), ("Royal Kludge", "RK84"), ("Corsair", "K70 RGB Pro"), ("EvoFox", "Katana")],
    "Office Membrane": [("Logitech", "K120"), ("Dell", "KB216"), ("HP", "K1500"), ("Zebronics", "Zeb-K20")],
    "Gaming Mouse": [("Logitech G", "G502 HERO"), ("Razer", "DeathAdder Essential"), ("SteelSeries", "Rival 3"), ("Redragon", "M711 Cobra")],
    "Travel Mouse": [("Logitech", "Pebble Mouse 2 M350s"), ("Microsoft", "Bluetooth Mouse"), ("HP", "Z3700"), ("Portronics", "Toad 23")],
    "Ergonomic Mouse": [("Logitech", "MX Vertical"), ("Logitech", "Lift Vertical"), ("Microsoft", "Sculpt Ergonomic Mouse"), ("Anker", "Vertical Ergonomic Mouse")],
    "Wireless Mouse": [("Logitech", "M331 Silent Plus"), ("Logitech", "MX Master 3S"), ("HP", "X200"), ("Dell", "MS3320W")],
    "4K Monitor": [("LG", "27UL550 27-inch 4K"), ("Samsung", "ViewFinity S8 27-inch"), ("Dell", "S2722QC 27-inch 4K"), ("BenQ", "EW2880U 28-inch")],
    "Office Monitor": [("Dell", "SE2422H 24-inch"), ("LG", "24MP400 24-inch"), ("Acer", "EK220Q 21.5-inch"), ("Samsung", "LS24C310 24-inch")],
    "Ultrawide": [("LG", "34WP65C 34-inch UltraWide"), ("Samsung", "Odyssey G5 34-inch"), ("Dell", "S3422DW 34-inch"), ("MSI", "MAG 342CQR")],
    "Gaming Monitor": [("ASUS", "TUF VG249Q1A 165Hz"), ("Acer", "Nitro VG240Y 180Hz"), ("LG", "UltraGear 27GN750"), ("BenQ", "MOBIUZ EX2510S")],
    "Portable Monitor": [("ASUS", "ZenScreen MB16ACV"), ("Lenovo", "ThinkVision M14"), ("ViewSonic", "VA1655"), ("Portronics", "Monitor 2")],
    "WiFi Router": [("TP-Link", "Archer C6 AC1200"), ("TP-Link", "Archer AX23 WiFi 6"), ("D-Link", "DIR-825"), ("Netgear", "R6350")],
    "USB WiFi Adapter": [("TP-Link", "Archer T2U Plus"), ("TP-Link", "TL-WN725N Nano"), ("D-Link", "DWA-131"), ("Tenda", "U9")],
    "Range Extender": [("TP-Link", "RE305 AC1200"), ("TP-Link", "RE200"), ("Netgear", "EX6110"), ("Tenda", "A9")],
    "Network Switch": [("TP-Link", "TL-SG108 8-Port Gigabit"), ("D-Link", "DGS-1008A"), ("Netgear", "GS305"), ("TP-Link", "LS1005G")],
    "Powerline Kit": [("TP-Link", "TL-PA4010 KIT"), ("TP-Link", "TL-PA7017 KIT"), ("Netgear", "PLP1000"), ("D-Link", "DHP-601AV")],
    "Mesh System": [("TP-Link", "Deco M4 (3-pack)"), ("TP-Link", "Deco X20 WiFi 6"), ("Netgear", "Orbi RBK352"), ("Google", "Nest Wifi Pro")],
    "Charger": [("Apple", "20W USB-C Power Adapter"), ("Samsung", "25W Super Fast Charger"), ("Anker", "Nano 3 30W GaN"), ("Belkin", "BoostCharge Pro 65W"), ("Ambrane", "65W GaN Charger")],
    "Webcam": [("Logitech", "C270 HD Webcam"), ("Logitech", "C920 Pro HD"), ("HP", "w300 1080p"), ("Lenovo", "300 FHD Webcam")],
    "Memory Card": [("SanDisk", "Extreme microSDXC 128GB"), ("Samsung", "EVO Plus microSD 128GB"), ("SanDisk", "Ultra microSDXC 64GB"), ("Kingston", "Canvas Select Plus 128GB")],
    "Power Bank": [("Mi", "Power Bank 3i 20000mAh"), ("Ambrane", "Stylo 10000mAh"), ("Anker", "PowerCore 20K"), ("boAt", "EnergyShroom PB300")],
    "Cable": [("Anker", "PowerLine III USB-C 2m"), ("Belkin", "Braided USB-C to Lightning"), ("Amazon Basics", "USB-C to USB-C 2.0"), ("Portronics", "Konnect A 1.2m")],
    "Laptop Bag": [("Wildcraft", "Evo 35L Laptop Backpack"), ("American Tourister", "Valex 28L"), ("Lenovo", "B210 Casual Backpack"), ("Skybags", "Brat 46cm")],
    "Phone Case": [("Spigen", "Ultra Hybrid Case"), ("Apple", "Silicone Case with MagSafe"), ("OtterBox", "Commuter Series"), ("Ringke", "Fusion Clear Case")],
    "USB Hub": [("Anker", "7-in-1 USB-C Hub"), ("UGREEN", "4-Port USB 3.0 Hub"), ("TP-Link", "UH400"), ("Portronics", "Mport 7C")],
    "Screen Protector": [("Spigen", "GlasTR EZ Fit Tempered Glass"), ("ZAGG", "InvisibleShield Glass Elite"), ("Belkin", "UltraGlass Screen Protector"), ("Amazon Basics", "Tempered Glass (2-pack)")],
    "Laptop Stand": [("AmazonBasics", "Adjustable Laptop Stand"), ("Portronics", "My Buddy K"), ("Rain Design", "mStand"), ("STRIFF", "Laptop Stand")],
    "Mousepad XL": [("Logitech G", "G840 XL Mouse Pad"), ("Razer", "Gigantus V2 XXL"), ("SteelSeries", "QcK Heavy XXL"), ("Cosmic Byte", "Equinox XL")],
    "VR Headset": [("Meta", "Quest 3 128GB"), ("Meta", "Quest 2 128GB"), ("Sony", "PlayStation VR2"), ("Pico", "4 Ultra")],
    "Gaming Chair": [("Green Soul", "Monster Ultimate"), ("ASE Gaming", "Lite Series"), ("Cellbell", "GC03"), ("DXRacer", "Formula Series")],
    "Gaming Console Accessory": [("Sony", "PS5 DualSense Charging Station"), ("Microsoft", "Xbox Rechargeable Battery Kit"), ("Nintendo", "Switch Pro Controller"), ("Sony", "PS5 Media Remote")],
    "Capture Card": [("Elgato", "HD60 X"), ("Elgato", "Cam Link 4K"), ("AVerMedia", "Live Gamer Mini"), ("Razer", "Ripsaw HD")],
    "Controller": [("Sony", "DualSense Wireless Controller"), ("Microsoft", "Xbox Wireless Controller"), ("Cosmic Byte", "Stellaris Wireless"), ("EvoFox", "Elite Play")],
}
VARIANTS = {"Smartphones": ["8GB/128GB", "8GB/256GB", "12GB/256GB", "12GB/512GB"],
            "Laptops": ["16GB/512GB SSD", "16GB/1TB SSD", "8GB/512GB SSD", "32GB/1TB SSD"],
            "Tablets": ["Wi-Fi 128GB", "Wi-Fi + 5G 128GB", "Wi-Fi 256GB", "Wi-Fi 64GB"]}

photos = json.loads((DATA / "product_photos.json").read_text())
p = pd.read_csv(DATA / "products.csv", dtype=str, keep_default_na=False)
old_names, old_brands = dict(zip(p.product_id, p.product_name)), dict(zip(p.product_id, p.brand))
used, new_name, new_brand, images, counters = set(), {}, {}, {}, {}
for _, r in p.iterrows():
    sub = r.subcategory
    i = counters.get(sub, 0)
    counters[sub] = i + 1
    opts = MODELS[sub]
    brand, model = opts[i % len(opts)]
    extra = VARIANTS.get(r.category, [""])
    for k in range(len(extra) * 4):
        bits = [x for x in (r.color, extra[k % len(extra)]) if x]
        name = f"{brand} {model} ({', '.join(bits)})" if bits else f"{brand} {model}"
        if k >= len(extra):  # still clashing: step to the next model in the subcategory
            brand, model = opts[(i + k // len(extra)) % len(opts)]
            name = f"{brand} {model} ({', '.join(bits)})" if bits else f"{brand} {model}"
        if name not in used:
            break
    used.add(name)
    new_name[r.product_id], new_brand[r.product_id] = name, brand
    ids = photos[sub]
    images[r.product_id] = f"https://images.unsplash.com/photo-{ids[i % len(ids)]}?auto=format&fit=crop&w=600&q=70"

# longest old name first so "X Pro" is replaced before "X"
pairs = sorted(((old_names[k], new_name[k]) for k in new_name), key=lambda x: -len(x[0]))
rx = re.compile("|".join(re.escape(o) for o, _ in pairs) + r"(?![\w])")
lookup = dict(pairs)


def rename(text: str) -> str:
    return rx.sub(lambda m: lookup[m.group(0)], text)


p["description"] = [rename(d).replace(f"from {old_brands[i]}", f"from {new_brand[i]}") for i, d in zip(p.product_id, p.description)]
p["product_name"] = p.product_id.map(new_name)
p["brand"] = p.product_id.map(new_brand)
p["image_url"] = p.product_id.map(images)
p.to_csv(DATA / "products.csv", index=False)

path = DATA / "conversations.json"
path.write_text(rename(path.read_text(encoding="utf-8")), encoding="utf-8")
for f in ("support_tickets.csv", "reviews.csv"):  # cell by cell: new names contain commas
    df = pd.read_csv(DATA / f, dtype=str, keep_default_na=False)
    df.map(rename).to_csv(DATA / f, index=False)

for md in (DATA / "products").glob("*.md"):
    parts = rename(md.read_text(encoding="utf-8")).split("\n## ")
    for n, part in enumerate(parts[1:], 1):
        m = re.search(r"\((PROD-\d+)\)", part.splitlines()[0])
        if m:
            pid = m.group(1)
            part = part.replace(f"**Brand:** {old_brands[pid]}", f"**Brand:** {new_brand[pid]}")
            parts[n] = part.replace(f"from {old_brands[pid]}", f"from {new_brand[pid]}")
    md.write_text("\n## ".join(parts), encoding="utf-8")

(DATA / "product_rename_map.json").write_text(json.dumps({k: [old_names[k], new_name[k]] for k in new_name}, indent=1))
print(f"renamed {len(new_name)} products; e.g. {old_names['PROD-00001']} -> {new_name['PROD-00001']}")
