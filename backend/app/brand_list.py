"""Starter blocklist: well-known brands to keep out of the store.

Why: big brands are the ones that file eBay VeRO takedowns against unauthorized resellers, and
buyers can compare a famous brand straight against Amazon. Small private-label brands are the
sweet spot for this business. This is a curated starting point, not an official or complete list
(eBay's VeRO program has thousands of members) — review it and add to it from Settings → Blocklist.

Two kinds of brand entries:
- ANYWHERE: distinctive names, matched in the product's brand, title and description, which also
  catches accessories such as "for KitchenAid mixer" (those still draw takedowns).
- EXACT: brands that are also everyday words ("Apple", "Shark", "Ring"), matched only against the
  product's actual brand, so "apple slicer" or "key ring" aren't blocked.
"""

ANYWHERE = """
# Electronics, phones, computers, smart home
AirPods, Beats by Dre, Bose, JBL, Harman Kardon, Bang & Olufsen, Sennheiser, Skullcandy, Jabra, Sonos, Logitech,
Razer, Corsair, SteelSeries, HyperX, Turtle Beach, Xbox, PlayStation, Nintendo, Garmin, Fitbit, GoPro, DJI,
Nikon, Fujifilm, Panasonic, Dyson, iRobot, Roomba, Anker, Belkin, Mophie, OtterBox, LifeProof, PopSockets,
Kindle, Fire TV, Roku, Amazon Basics, AmazonBasics, Arlo, Wyze, Eufy, Chromecast, Western Digital, SanDisk,
Seagate, Nvidia, Lenovo, Toshiba, Cricut, Epson, Theragun, Therabody, Hyperice, Oura, Peloton, Bowflex,
NordicTrack, Samsung, Sony, Microsoft, Philips, Bissell, Instant Pot, Crock-Pot, Ring Doorbell, Echo Dot,
Google Nest, Apple Watch, MacBook, iPad, Magic Mouse, Ninja Foodi, Shark Navigator, Shark Rotator

# Kitchen, home, cleaning
KitchenAid, Le Creuset, Staub, All-Clad, Cuisinart, Calphalon, OXO, Pyrex, CorningWare, Corelle, Rubbermaid,
Tupperware, Zwilling, Henckels, Wusthof, Victorinox, Vitamix, Blendtec, NutriBullet, Hamilton Beach,
Black+Decker, Black & Decker, Breville, Keurig, Nespresso, De'Longhi, DeLonghi, Mr. Coffee, Bodum, Chemex, Hario,
Hydro Flask, Yeti, Owala, Contigo, CamelBak, Nalgene, S'well, Thermos, Zojirushi, Brita, ZeroWater, SodaStream,
Chefman, Cosori, Traeger, Solo Stove, Coleman, RTIC, Pit Boss, Kamado Joe, Big Green Egg, Joseph Joseph,
Simplehuman, Libbey, Lodge Cast Iron, Swiffer, Clorox, Lysol, Febreze, Mrs. Meyer's, Seventh Generation, Tide,
Downy, Charmin, Hefty, Ziploc, Reynolds Wrap, 3M, Post-it, Sharpie, Crayola, Elmer's, Gorilla Glue, Loctite,
WD-40, Rust-Oleum, Purell, Scotch-Brite, Command Strips, Ball Mason, Weber Grill, Blackstone Griddle, Igloo Cooler,
Mason Cash, Stasher, Bormioli, Anchor Hocking, Farberware, T-fal, Tefal, Rachael Ray, Pioneer Woman, Ninja Creami

# Tools & hardware
DeWalt, Milwaukee, Makita, Ryobi, Craftsman, Snap-on, Klein Tools, Kobalt, Festool, Hilti, Metabo, Ridgid,
Dremel, Leatherman, Benchmade, Kershaw, Ka-Bar, Fiskars, Greenworks, Sun Joe, Channellock, Knipex, Wera, Wiha,
Fluke, Maglite, Streamlight, Olight, Energizer, Duracell, Rayovac, Eveready, Irwin Tools, Bosch, Stanley Tools,
Husky Tools, Worx, Gerber Gear, Buck Knives, Spyderco, Zippo, Weller, Estwing, Vise-Grip, Werner Ladder

# Toys, kids, baby
Lego, Mattel, Hasbro, Hot Wheels, Fisher-Price, Little Tikes, Melissa & Doug, Play-Doh, Nerf, Monopoly, Funko,
Pokemon, Disney, Pixar, Star Wars, Harry Potter, Paw Patrol, Peppa Pig, Bluey, Cocomelon, Sesame Street,
Squishmallows, Hello Kitty, Sanrio, Minecraft, Roblox, Fortnite, Super Mario, Spider-Man, Spiderman, Batman,
Superman, Avengers, Bratz, LOL Surprise, Beanie Babies, Jellycat, VTech, LeapFrog, Magna-Tiles, Hatchimals,
Spin Master, Graco, Chicco, Baby Jogger, UPPAbaby, Britax, Evenflo, Pampers, Huggies, Dr. Brown's,
Philips Avent, Tommee Tippee, Skip Hop, Owlet, Nanit, Hatch Rest, Barbie, Polly Pocket, Transformers,
Power Rangers, My Little Pony, Care Bears, Teenage Mutant Ninja Turtles, Thomas & Friends,
Toy Story, Minions, SpongeBob, Nickelodeon, Looney Tunes, DreamWorks, Warner Bros, Universal Studios, WWE,
Stranger Things, Star Trek, Lord of the Rings, Game of Thrones, Taylor Swift, Kidkraft, Radio Flyer, Step2

# Clothing, shoes, bags, jewelry, watches, eyewear
Nike, Adidas, Reebok, Asics, Skechers, Hoka, Saucony, New Balance, Under Armour, Lululemon, Gymshark, Carhartt,
Levi's, Wrangler, Patagonia, The North Face, North Face, Arc'teryx, Canada Goose, Ugg, Birkenstock,
Dr. Martens, Timberland, Steve Madden, Michael Kors, Kate Spade, Tory Burch, Casio, Seiko, Rolex, Tag Heuer,
Ray-Ban, Oakley, Maui Jim, Swarovski, Tiffany, Alex and Ani, Kendra Scott, Herschel, JanSport, Fjallraven,
Hanes, Fruit of the Loom, Calvin Klein, Tommy Hilfiger, Ralph Lauren, Old Navy, Victoria's Secret, Burberry,
Cartier, Chanel, Dior, Fendi, Gucci, Hermes, Louis Vuitton, Moncler, Prada, Versace, Vera Bradley, Samsonite,
Brooks Running, Columbia Sportswear, Pandora Jewelry, Vans Shoes, Air Jordan, Yeezy, Supreme,
Champion Athletic, Fossil Watch, Citizen Watch, Omega Watch, Costa Del Mar, Osprey Packs, Stanley Cup,
Quay Australia, Lacoste, Hugo Boss, Armani, Balenciaga, Givenchy, Valentino, Yves Saint Laurent, Bottega Veneta,
Off-White, Golden Goose, Christian Louboutin, Jimmy Choo, Marc Jacobs, Longchamp, Goyard, Mulberry, Coach Bag

# Beauty, personal care, health
Olaplex, CeraVe, Cetaphil, La Roche-Posay, Neutrogena, Olay, L'Oreal, Maybelline, NYX, e.l.f. Cosmetics,
Clinique, Estee Lauder, MAC Cosmetics, Urban Decay, Too Faced, Benefit Cosmetics, Fenty Beauty, Kylie Cosmetics,
Rare Beauty, Charlotte Tilbury, Tarte, Anastasia Beverly Hills, Dermalogica, The Ordinary, Paula's Choice,
Drunk Elephant, Glossier, Moroccanoil, Paul Mitchell, Revlon, Redken, Conair, BaBylissPRO, Hot Tools, Wahl,
Andis, Philips Norelco, Braun, Gillette, Oral-B, Philips Sonicare, Sonicare, Waterpik, Crest, Colgate,
Burt's Bees, Nivea, Aveeno, Vaseline, Old Spice, Dr. Squatch, Bath & Body Works, Sephora, Ulta, Kiehl's,
Lancome, Shiseido, Sol de Janeiro, Laneige, Summer Fridays, Tatcha, SkinCeuticals, Mario Badescu, Bioderma,
Optimum Nutrition, Garden of Life, Nature Made, Centrum, Vital Proteins, Orgain, Premier Protein, Liquid I.V.,
Dyson Airwrap, T3 Micro, ghd Hair, Remington Shaver, Dove Soap, Native Deodorant

# Pets
Furminator, Petmate, PetSafe, Frontline, Seresto, NexGard, Purina, Blue Buffalo, Greenies, Dentastix, Nylabone,
Chuckit, Ruffwear, Kong Dog, Kurgo, Arm & Hammer

# Auto, sports, outdoor, office
WeatherTech, Meguiar's, Chemical Guys, Armor All, Turtle Wax, Michelin, Rain-X, NOCO, Thule, Husky Liners,
Spalding, Rawlings, Callaway, TaylorMade, Titleist, Selkirk, Joola, Babolat, Yonex, Bushnell, Leupold, Petzl,
Black Diamond Equipment, TRX Training, Hydrow, Paper Mate, Five Star, Moleskine, Rocketbook, Fellowes,
Wilson Sporting, Franklin Sports, Ping Golf, Vortex Optics, Yakima Racks, Cobra Golf, Expo Markers, Pilot Pen,
BIC Pen, Avery Labels, Brother Printer, Canon Camera, Canon Printer, HP Printer, Dell Laptop, Asus, Acer Laptop

# Licensed sports, cars and other famous marks
NFL, NBA, MLB, NHL, NCAA, FIFA, Coca-Cola, Pepsi, Harley-Davidson, John Deere, Caterpillar, Ferrari,
Lamborghini, Porsche, BMW, Mercedes-Benz, Ford Mustang, Chevrolet, Jeep Wrangler, Playboy, Marvel Comics, DC Comics
"""

# Everyday words — only blocked when they ARE the product's brand.
EXACT = """
Apple, Beats, Shark, Ninja, Coach, Ring, Echo, Blink, Dash, Command, Scotch, Lodge, Ball, Igloo, Weber, Blackstone,
Stanley, Brooks, Columbia, Converse, Vans, Jordan, Pandora, Marvel, Crocs, Champion, Fossil, Citizen, Omega,
Costa, Osprey, Puma, Gap, Google, Nest, Tile, Alexa, Tesla, Ember, Dove, Native, Method, Gain, Bounty, Scott,
Glad, Expo, Pilot, BIC, Avery, Brother, Canon, HP, Dell, LG, AMD, Intel, Hoover, Eureka, Husky, Irwin, Gerber,
EGO, Fenix, Kong, Advantage, Munchkin, Hatch, Fellow, Umbra, PUR, Tiger, Wilson, Franklin, Ping, Vortex,
Yakima, Cobra, Remington, T3, ghd, Celsius, Ghost, Frozen, Sonic, Mario, Ty, Whoop, Away, On, Hunter, Guess,
Nautica, Kodak, Polaroid, Instax, Acer, Schwinn, Huffy, Head, Prince, Dunlop
"""

KEYWORDS = ["replica", "knockoff", "counterfeit", "inspired by", "dupe", "1:1 copy", "aaa quality",
            "unbranded designer", "fake", "officially licensed", "licensed product", "authentic designer"]


def _parse(block: str) -> list[str]:
    out = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out += [t.strip() for t in line.split(",") if t.strip()]
    return out


def entries() -> list[tuple[str, str]]:
    """(term, kind) for the whole starter list."""
    return ([(t, "brand") for t in _parse(ANYWHERE)] + [(t, "brand_exact") for t in _parse(EXACT)]
            + [(k, "keyword") for k in KEYWORDS])
