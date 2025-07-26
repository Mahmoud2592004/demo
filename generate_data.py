import os
import json
import re
import random
import shutil
import sys
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
from rapidfuzz import process, fuzz
import unicodedata
import ast
from urllib.parse import unquote

# Set UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
random.seed(42)  # For reproducible results
THRESHOLD = 50  # Fuzzy matching threshold
START_DATE = datetime(2025, 7, 1)
END_DATE = datetime(2025, 7, 27)
DATE_RANGE = (END_DATE - START_DATE).days

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

PHARMACIES = [
    "Al Borg Pharmacy", "El Ezaby Pharmacy", "Seif Pharmacy", "Al Shams Pharmacy",
    "Misr Pharmacy", "19011 Pharmacy", "El Agamy Pharmacy", "Roushdy Pharmacy",
    "El Delta Pharmacy", "Normandy Pharmacy"
]

class MedicineMatcher:
    def __init__(self, drug_list):
        self.drug_list = drug_list
    
    def get_top_matches(self, query, topN=3):
        """Find top similar drugs using enhanced fuzzy matching"""
        query_lower = query.lower()
        exact_matches = [drug for drug in self.drug_list if query_lower in drug.lower()]
        if exact_matches:
            return [{"name": match, "score": 100.0} for match in exact_matches[:topN]]
        
        results = process.extract(
            query, 
            self.drug_list, 
            scorer=fuzz.token_sort_ratio, 
            limit=topN * 5
        )
        
        filtered = [res for res in results if res[1] >= THRESHOLD]
        if not filtered:
            return []
        
        filtered.sort(key=lambda x: x[1], reverse=True)
        return [{"name": result[0], "score": result[1]} for result in filtered[:topN]]
    
    @staticmethod
    def clean_text(text):
        """Clean text for better matching"""
        if not isinstance(text, str):
            return ""
            
        text = unicodedata.normalize('NFC', text)
        text = re.sub(r'[^\w\s\u0600-\u06FF]', '', text, flags=re.UNICODE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()

def ensure_min_prescriptions(records_list, min_per_city=5):
    """Ensure each city has at least min_per_city prescriptions with valid images and drugs, no duplicate images in same city"""
    prescriptions_with_images_and_drugs = [
        r for r in records_list 
        if r.get('image_path') and 
        isinstance(r['image_path'], str) and 
        os.path.exists(r['image_path']) and 
        r.get('drugs') and json.loads(r['drugs'])  # Ensure non-empty drugs list
    ]
    
    if not prescriptions_with_images_and_drugs:
        print("Warning: No prescriptions with valid images and drugs found in the dataset")
        return records_list
    
    all_cities = []
    for gov, cities in EGYPT_LOCATIONS.items():
        for city in cities:
            all_cities.append((gov, city))
    
    location_groups = {}
    image_to_cities = {}  # Track images used in each city
    for record in records_list:
        key = (record['governorate'], record['city'])
        if key not in location_groups:
            location_groups[key] = []
        location_groups[key].append(record)
        img_name = os.path.basename(record['image_path'])
        if img_name not in image_to_cities:
            image_to_cities[img_name] = set()
        image_to_cities[img_name].add(record['city'])
    
    duplicate_image_skipped = 0
    
    for gov, city in all_cities:
        key = (gov, city)
        current_with_images_and_drugs = len([
            r for r in location_groups.get(key, []) 
            if r.get('image_path') and os.path.exists(r['image_path']) and 
            r.get('drugs') and json.loads(r['drugs'])
        ])
        
        if current_with_images_and_drugs < min_per_city:
            needed = min_per_city - current_with_images_and_drugs
            available_sources = prescriptions_with_images_and_drugs.copy()
            for _ in range(needed):
                # Filter sources to avoid images already used in this city
                valid_sources = [
                    src for src in available_sources 
                    if os.path.basename(src['image_path']) not in image_to_cities or 
                    city not in image_to_cities[os.path.basename(src['image_path'])]
                ]
                
                if not valid_sources:
                    print(f"Warning: No available prescriptions without duplicate images for {gov}/{city}. Skipping.")
                    duplicate_image_skipped += 1
                    continue
                
                source = random.choice(valid_sources)
                new_record = source.copy()
                
                new_id = f"RX{len(records_list) + 1:04d}"
                new_record['prescription_id'] = new_id
                
                old_img_path = new_record['image_path']
                gov_folder = gov.replace('/', '-')
                city_folder = city.replace('/', '-')
                dest_folder = os.path.join("organized_images", gov_folder, city_folder)
                os.makedirs(dest_folder, exist_ok=True)
                
                img_name = os.path.basename(old_img_path)
                new_img_path = os.path.join(dest_folder, img_name)
                
                # Verify that the copied image exists before adding
                if old_img_path != new_img_path:
                    try:
                        shutil.copy(old_img_path, new_img_path)
                        if not os.path.exists(new_img_path):
                            print(f"Failed to copy image to {new_img_path}, skipping duplicate")
                            duplicate_image_skipped += 1
                            continue
                        new_record['image_path'] = new_img_path
                    except shutil.SameFileError:
                        new_record['image_path'] = old_img_path
                    except Exception as e:
                        print(f"Error copying image {img_name} for duplication: {e}")
                        duplicate_image_skipped += 1
                        continue
                
                # Update image_to_cities tracking
                if img_name not in image_to_cities:
                    image_to_cities[img_name] = set()
                image_to_cities[img_name].add(city)
                
                new_record['governorate'] = gov
                new_record['city'] = city
                records_list.append(new_record)
                if key not in location_groups:
                    location_groups[key] = []
                location_groups[key].append(new_record)
    
    print(f"- Duplicates skipped due to image conflicts: {duplicate_image_skipped}")
    return records_list

def extract_drugs_from_confirmed(confirmed_drugs):
    """Extract drug names from confirmedDrugs column with 100% score"""
    if pd.isna(confirmed_drugs) or confirmed_drugs in ["", "null", "None"]:
        return []
        
    try:
        if isinstance(confirmed_drugs, str):
            try:
                drugs_data = json.loads(confirmed_drugs)
            except json.JSONDecodeError:
                try:
                    drugs_data = ast.literal_eval(confirmed_drugs)
                except:
                    drugs_data = confirmed_drugs
        else:
            drugs_data = confirmed_drugs
            
        if isinstance(drugs_data, list):
            return [{"name": item.get('name', ''), "score": 100.0} 
                    for item in drugs_data if 'name' in item]
    except Exception as e:
        print(f"Error extracting confirmed drugs: {e}")
        return []
        
    return []

def extract_doctor_name(text):
    """Extract doctor name from text with multilingual support"""
    if not text or not isinstance(text, str):
        return None
        
    text = unicodedata.normalize('NFC', text)
    
    arabic_patterns = [
        r'(دكتور|الدكتور|د\.|د)\s*([^\n]+?)(?=\n|$|\.|,)',
        r'(دكتور|الدكتور|د\.|د)\s*([^\n]+)'
    ]
    
    english_patterns = [
        r'(dr\.?|doctor)\s*([^\n]+?)(?=\n|$|\.|,)',
        r'(dr\.?|doctor)\s*([^\n]+)'
    ]
    
    for pattern in arabic_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(2).strip()
            name = re.sub(r'[^\w\s\u0600-\u06FF]+$', '', name)
            return name
    
    for pattern in english_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(2).strip()
            name = re.sub(r'[^\w\s]+$', '', name)
            return name
            
    return None

def extract_text_from_field(field_data):
    """Extract text from fullTextAnnotation or textAnnotations field"""
    if pd.isna(field_data) or field_data in ["", "null", "None"]:
        return ""
    
    text = ""
    
    if isinstance(field_data, str):
        try:
            parsed = json.loads(field_data)
            if isinstance(parsed, dict):
                text = parsed.get('text', '')
            elif isinstance(parsed, list) and parsed:
                if 'description' in parsed[0]:
                    text = parsed[0].get('description', '')
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(field_data)
                if isinstance(parsed, dict):
                    text = parsed.get('text', '')
                elif isinstance(parsed, list) and parsed:
                    if 'description' in parsed[0]:
                        text = parsed[0].get('description', '')
            except:
                text = field_data
    elif isinstance(field_data, dict):
        text = field_data.get('text', '')
    elif isinstance(field_data, list) and field_data:
        if 'description' in field_data[0]:
            text = field_data[0].get('description', '')
    
    return text

def process_prescriptions(input_file, drug_db_file, image_source_dir="raw_images"):
    """Process prescriptions by scanning images first and matching to Excel data"""
    print("Loading data...")
    try:
        # Load prescriptions data
        df = pd.read_excel(input_file)
        
        # Load drug database
        drug_db = pd.read_excel(drug_db_file, sheet_name='Merged Data')
        drug_list = drug_db['Name'].tolist()
        print(f"Loaded {len(drug_list)} drugs from database")
        matcher = MedicineMatcher(drug_list)
        
        # Create output folder
        os.makedirs("organized_images", exist_ok=True)
        
        processed_data = []
        doctor_names = []
        confirmed_count = 0
        text_extracted_count = 0
        unmatched_images = 0
        no_drugs_skipped = 0
        mixed_drugs_count = 0
        duplicate_image_skipped = 0
        
        # Scan all images in the source directory (recursive)
        image_paths = []
        for root, _, files in os.walk(image_source_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    image_paths.append(os.path.join(root, file))
        
        print(f"Found {len(image_paths)} images in {image_source_dir}")
        
        # Create a lookup dictionary for Excel data by image name
        image_to_record = {}
        for idx, row in df.iterrows():
            image_url = row.get('imageUrl', '')
            if not image_url:
                continue
            decoded_url = unquote(image_url)
            image_name = os.path.basename(decoded_url).split('?')[0].lower().strip()
            image_to_record[image_name] = row
        
        # Track images used in each city
        image_to_cities = {}
        
        # Process each image
        for idx, image_path in enumerate(image_paths):
            if idx % 10 == 0:
                print(f"Processing image {idx+1}/{len(image_paths)}")
            
            image_name = os.path.basename(image_path).lower().strip()
            record = image_to_record.get(image_name)
            
            if record is None:
                print(f"No matching record found for image: {image_name}")
                unmatched_images += 1
                # Create a minimal record for unmatched images
                prescription_id = f"RX{len(processed_data) + 1:04d}"
                drugs = []
                doctor_name = "Not detected"
            else:
                prescription_id = record.get('id', f"RX{len(processed_data) + 1:04d}")
                # Extract drugs from confirmedDrugs if available
                confirmed_drugs = record.get('confirmedDrugs', None)
                drugs = extract_drugs_from_confirmed(confirmed_drugs)
                if drugs:
                    confirmed_count += 1
                    print(f"Found {len(drugs)} confirmed drugs for image {image_name}")
                
                # Extract text for doctor name and drugs (if no confirmed drugs)
                full_text = extract_text_from_field(record.get('fullTextAnnotation', None))
                annotations_text = extract_text_from_field(record.get('textAnnotations', None))
                text = full_text if len(full_text) > len(annotations_text) else annotations_text
                
                if text:
                    text_extracted_count += 1
                    # Extract doctor name
                    doctor_name = extract_doctor_name(text)
                    if doctor_name:
                        try:
                            print(f"Found doctor: {doctor_name} for image {image_name}")
                        except UnicodeEncodeError:
                            print(f"Found doctor (name: {doctor_name.encode('utf-8')}) for image {image_name}")
                    
                    # Extract drugs from text only if no confirmed drugs
                    if not drugs:
                        lines = text.split('\n')
                        for line in lines:
                            if doctor_name and doctor_name in line:
                                continue
                            if any(keyword in line for keyword in ['دكتور', 'الدكتور', 'د.', 'د', 'dr', 'doctor']):
                                continue
                            clean_line = MedicineMatcher.clean_text(line)
                            if len(clean_line) > 3:
                                matches = matcher.get_top_matches(clean_line, topN=1)
                                if matches and matches[0]['score'] >= THRESHOLD:
                                    drugs.append(matches[0])
                                    print(f"Matched drug: {matches[0]['name']} (score: {matches[0]['score']})")
            
            # Skip prescriptions with no drugs
            if not drugs:
                print(f"Skipping prescription for image {image_name}: No confirmed or detected drugs")
                no_drugs_skipped += 1
                continue
            
            # Validate drugs list to ensure no mixed confirmed and detected drugs
            has_confirmed = any(drug['score'] == 100.0 for drug in drugs)
            has_detected = any(drug['score'] < 100.0 for drug in drugs)
            if has_confirmed and has_detected:
                mixed_drugs_count += 1
                print(f"Warning: Prescription {prescription_id} has both confirmed and detected drugs. Keeping only confirmed drugs.")
                drugs = [drug for drug in drugs if drug['score'] == 100.0]
            
            # Skip if no drugs remain after validation
            if not drugs:
                print(f"Skipping prescription for image {image_name}: No valid drugs after validation")
                no_drugs_skipped += 1
                continue
            
            # Assign random location
            governorate = random.choice(list(EGYPT_LOCATIONS.keys()))
            city = random.choice(EGYPT_LOCATIONS[governorate])
            
            # Check if image is already used in this city
            if image_name in image_to_cities and city in image_to_cities[image_name]:
                print(f"Skipping prescription for image {image_name}: Image already used in {city}")
                duplicate_image_skipped += 1
                continue
            
            # Update image_to_cities tracking
            if image_name not in image_to_cities:
                image_to_cities[image_name] = set()
            image_to_cities[image_name].add(city)
            
            # Assign random pharmacy
            pharmacy = random.choice(PHARMACIES)
            
            # Assign random timestamp between July 1-27, 2025
            random_days = random.randint(0, DATE_RANGE)
            timestamp = START_DATE + timedelta(days=random_days)
            
            # Organize image
            gov_folder = governorate.replace('/', '-')
            city_folder = city.replace('/', '-')
            dest_folder = os.path.join("organized_images", gov_folder, city_folder)
            os.makedirs(dest_folder, exist_ok=True)
            dest_image_path = os.path.join(dest_folder, image_name)
            
            # Copy image and verify it exists
            try:
                if image_path != dest_image_path:
                    shutil.copy(image_path, dest_image_path)
                if not os.path.exists(dest_image_path):
                    print(f"Image {image_name} not found at {dest_image_path}, skipping")
                    duplicate_image_skipped += 1
                    continue
            except shutil.SameFileError:
                dest_image_path = image_path
            except Exception as e:
                print(f"Error copying image {image_name}: {e}")
                duplicate_image_skipped += 1
                continue
            
            # Only include prescriptions with valid images and drugs in processed_data
            processed_data.append({
                "prescription_id": prescription_id,
                "governorate": governorate,
                "city": city,
                "pharmacy": pharmacy,
                "drugs": json.dumps(drugs, ensure_ascii=False),
                "doctor_name": doctor_name or "Not detected",
                "timestamp": timestamp.strftime("%Y-%m-%d"),
                "image_path": dest_image_path
            })
            
            # Only append doctor_name if image is valid and drugs are present
            if doctor_name and doctor_name != "Not detected":
                doctor_names.append(doctor_name)
        
        print(f"\nProcessing summary:")
        print(f"- Total images processed: {len(image_paths)}")
        print(f"- Images with matching records: {len(image_paths) - unmatched_images}")
        print(f"- Images without matching records: {unmatched_images}")
        print(f"- Prescriptions with confirmed drugs: {confirmed_count}")
        print(f"- Prescriptions with extracted text: {text_extracted_count}")
        print(f"- Prescriptions with mixed confirmed and detected drugs: {mixed_drugs_count}")
        print(f"- Prescriptions skipped due to no drugs: {no_drugs_skipped}")
        print(f"- Prescriptions skipped due to duplicate images in city: {duplicate_image_skipped}")
        print(f"- Prescriptions with valid images and drugs included: {len(processed_data)}")
        print(f"- Doctor names detected: {len(doctor_names)}")
        
        # Ensure each city has at least 5 prescriptions with images and drugs
        processed_data = ensure_min_prescriptions(processed_data, min_per_city=5)
        print(f"- Total after ensuring minimum per city: {len(processed_data)}")
        
        # Create final DataFrame
        output_df = pd.DataFrame(processed_data)
        
        # Save doctor insights
        if doctor_names:
            doctor_counts = pd.Series(doctor_names).value_counts().reset_index()
            doctor_counts.columns = ['doctor_name', 'prescription_count']
            doctor_counts.to_excel("doctor_insights.xlsx", index=False)
            print(f"- Saved insights for {len(doctor_counts)} doctors")
        
        return output_df
        
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def save_data(df):
    """Save all data to Excel with reference sheets"""
    if df.empty:
        print("No data to save")
        return
    
    os.makedirs("output", exist_ok=True)
    
    with pd.ExcelWriter("output/processed_prescriptions.xlsx") as writer:
        df.to_excel(writer, sheet_name="Prescriptions", index=False)
        
        location_data = []
        for gov, cities in EGYPT_LOCATIONS.items():
            for city in cities:
                location_data.append({"Governorate": gov, "City": city})
        pd.DataFrame(location_data).to_excel(writer, sheet_name="Locations", index=False)
        
        pd.DataFrame({"Pharmacy": PHARMACIES}).to_excel(writer, sheet_name="Pharmacies", index=False)
        
        if os.path.exists("doctor_insights.xlsx"):
            doctor_df = pd.read_excel("doctor_insights.xlsx")
            doctor_df.to_excel(writer, sheet_name="Doctors", index=False)

if __name__ == "__main__":
    # Configuration
    INPUT_FILE = "prescriptions.xlsx"
    DRUG_DB_FILE = "search engine MedDigi.xlsx"
    
    print("Starting prescription processing...")
    processed_df = process_prescriptions(INPUT_FILE, DRUG_DB_FILE)
    
    if not processed_df.empty:
        print("Saving processed data...")
        save_data(processed_df)
        print(f"""
        Processing complete!
        - Total prescriptions processed: {len(processed_df)}
        - Output file: output/processed_prescriptions.xlsx
        """)
    else:
        print("No prescriptions were processed. Please check input files and folders.")