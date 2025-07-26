import os
import random
import shutil
import pandas as pd
from datetime import datetime, timedelta
import string

# Configuration
random.seed(42)  # For reproducible results

EGYPT_LOCATIONS = {
    "Cairo": ["Cairo", "Nasr City", "Heliopolis", "Maadi", "Shubra"],
    "Giza": ["Giza", "6th of October City", "Sheikh Zayed City", "Haram District", "Imbaba"],
    "Alexandria": ["Alexandria", "Borg El Arab", "Amreya", "Sidi Gaber", "Montaza"],
    "Qalyubia": ["Qalyubia", "Banha", "Qalyub", "Shubra El Kheima", "Khanka", "Tokh"],
    "Sharqia": ["Sharqia", "Zagazig", "10th of Ramadan", "Belbeis", "Abu Kabir", "Minya Al Qamh"],
    "Dakahlia": ["Dakahlia", "Mansoura", "Talkha", "Mit Ghamr", "Sherbin", "Aga"],
    "Beheira": ["Beheira", "Damanhur", "Kafr El Dawwar", "Edku", "Rosetta", "Abu Hummus"],
    "Kafr El Sheikh": ["Kafr El Sheikh", "Desouk", "Baltim", "Sidi Salem", "Fuwwah"],
    "Gharbia": ["Gharbia", "Tanta", "El Mahalla El Kubra", "Kafr El Zayat", "Zefta", "Samannoud"],
    "Menoufia": ["Menoufia", "Shebin El Kom", "Quesna", "Ashmoun", "Menouf", "Sadat City"],
    "Ismailia": ["Ismailia", "Fayed", "Abu Suwayr", "Qantara West", "Tell El Kebir"],
    "Port Said": ["Port Said", "Port Fouad", "El Manakh", "El Zohour", "Arab District"],
    "Suez": ["Suez", "Ataqah", "Ain Sokhna", "Arbaeen District", "Faisal District"],
    "Damietta": ["Damietta", "New Damietta", "Faraskur", "Kafr Saad", "Ras El Bar"],
    "Faiyum": ["Faiyum", "Sinnuris", "Ibshaway", "Tamiya", "Yousef El Sediq"],
    "Beni Suef": ["Beni Suef", "El Wasta", "Nasser City", "Biba", "Ihnasia"],
    "Minya": ["Minya", "Mallawi", "Samalut", "Beni Mazar", "Maghagha"],
    "Assiut": ["Assiut", "Dayrout", "Manfalut", "Abu Tig", "El Quseyya"],
    "Sohag": ["Sohag", "Tahta", "Akhmim", "Girga", "El Balyana"],
    "Qena": ["Qena", "Nag Hammadi", "Qus", "Deshna", "Abu Tesht"],
    "Luxor": ["Luxor", "Armant", "Esna", "Tod", "Karnak"],
    "Aswan": ["Aswan", "Edfu", "Kom Ombo", "Daraw", "Abu Simbel"],
    "Red Sea Governorate": ["Hurghada", "Safaga", "El Quseir", "Marsa Alam", "Ras Gharib"],
    "New Valley Governorate": ["Kharga Oasis", "Dakhla Oasis", "Farafra Oasis", "Baris", "Balat"],
    "Matrouh": ["Marsa Matruh", "El Alamein", "Siwa Oasis", "Sidi Barrani", "Sallum"],
    "North Sinai": ["Arish", "Sheikh Zuweid", "Rafah", "Bir al-Abed", "Nakhl"],
    "South Sinai": ["Sharm El Sheikh", "Dahab", "Nuweiba", "Saint Catherine", "Taba"]
}

PHARMACIES = ["Al Borg", "Seif", "Nile", "HealthFirst", "Cairo Care"]
DRUGS = ["Paracetamol", "Amoxicillin", "Ibuprofen", "Omeprazole", "Cetirizine"]
ARABIC_NAMES = ["Ahmed", "Mohamed", "Mahmoud", "Ali", "Omar", "Youssef", "Ibrahim", 
               "Fatima", "Aisha", "Mariam", "Nour", "Huda"]

def generate_name():
    """Generate Arabic-sounding names without Faker"""
    first = random.choice(ARABIC_NAMES)
    last = random.choice(["Al-Masry", "El-Sayed", "Abdullah", "Hassan", "Farouk"])
    return f"{first} {last}"

def generate_synthetic_prescriptions(min_per_city=5):
    """Generate synthetic prescription data ensuring minimum per city"""
    prescriptions = []
    prescription_id = 1
    
    # First pass: Ensure minimum prescriptions per city
    for gov, cities in EGYPT_LOCATIONS.items():
        for city in cities:
            for _ in range(min_per_city):
                prescriptions.append({
                    "prescription_id": f"RX{prescription_id:04d}",
                    "governorate": gov,
                    "city": city,
                    "pharmacy": random.choice(PHARMACIES),
                    "drugs": ", ".join(random.sample(DRUGS, random.randint(1, 3))),
                    "timestamp": (datetime(2025, 7, 1) + timedelta(days=random.randint(0, 26))).strftime("%Y-%m-%d"),
                    "patient_name": generate_name(),
                    "patient_age": random.randint(18, 80),
                    "patient_gender": random.choice(["Male", "Female"])
                })
                prescription_id += 1
    
    # Second pass: Add random distribution (30% more)
    additional_records = int(len(prescriptions) * 0.3)
    for _ in range(additional_records):
        gov = random.choice(list(EGYPT_LOCATIONS.keys()))
        city = random.choice(EGYPT_LOCATIONS[gov])
        
        prescriptions.append({
            "prescription_id": f"RX{prescription_id:04d}",
            "governorate": gov,
            "city": city,
            "pharmacy": random.choice(PHARMACIES),
            "drugs": ", ".join(random.sample(DRUGS, random.randint(1, 3))),
            "timestamp": (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            "patient_name": generate_name(),
            "patient_age": random.randint(18, 80),
            "patient_gender": random.choice(["Male", "Female"])
        })
        prescription_id += 1
    
    return prescriptions

def organize_images(prescriptions, image_source_dir="raw_images"):
    """Organize images to match the generated data"""
    os.makedirs("organized_images", exist_ok=True)
    
    # Get all available images
    all_images = [f for f in os.listdir(image_source_dir) 
                 if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not all_images:
        raise FileNotFoundError(f"No images found in {image_source_dir}")
    
    # Distribute images
    for idx, prescription in enumerate(prescriptions):
        gov = prescription['governorate'].replace("/", "-")  # Sanitize path
        city = prescription['city'].replace("/", "-")
        
        # Create city directory
        city_dir = f"organized_images/{gov}/{city}"
        os.makedirs(city_dir, exist_ok=True)
        
        # Copy image (cycle through available images)
        img_src = os.path.join(image_source_dir, all_images[idx % len(all_images)])
        img_dest = f"{city_dir}/prescription_{prescription['prescription_id']}.jpg"
        shutil.copy(img_src, img_dest)
        
        # Update path in data
        prescription['image_path'] = img_dest

def save_data(prescriptions):
    """Save all data to Excel"""
    df = pd.DataFrame(prescriptions)
    
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    with pd.ExcelWriter("output/prescription_data.xlsx") as writer:
        df.to_excel(writer, sheet_name="Prescriptions", index=False)
        
        # Create reference sheets
        pd.DataFrame({
            "Governorate": [gov for gov, cities in EGYPT_LOCATIONS.items() for _ in cities],
            "City": [city for cities in EGYPT_LOCATIONS.values() for city in cities]
        }).to_excel(writer, sheet_name="Locations", index=False)
        
        pd.DataFrame({"Pharmacy": PHARMACIES}).to_excel(writer, sheet_name="Pharmacies", index=False)

if __name__ == "__main__":
    print("Generating synthetic prescriptions...")
    prescriptions = generate_synthetic_prescriptions(min_per_city=5)
    
    print("Organizing images...")
    try:
        organize_images(prescriptions)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Continuing without images.")
        for p in prescriptions:
            p['image_path'] = ""
    
    print("Saving data...")
    save_data(prescriptions)
    
    print(f"""
    Data generation complete!
    - Total prescriptions: {len(prescriptions)}
    - Cities covered: {sum(len(c) for c in EGYPT_LOCATIONS.values())}
    - Output file: output/prescription_data.xlsx
    """)