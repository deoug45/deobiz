# create_user.py
import bcrypt
from supabase import create_client
from config import Config

# Connect to Supabase
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

def create_user(name, email, password, phone=""):
    # Hash the password
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    # Insert into clients table
    data = {
        "name": name,
        "email": email,
        "phone": phone,
        "password": hashed  # make sure your app reads this column
    }
    
    response = supabase.table("clients").insert(data).execute()
    print("User created:", response)

if __name__ == "__main__":
    name = "Ayebare Deogratious"
    email = "deoug45@gmail.com"
    password = "YourStrongPassword123"
    phone = "0000000000"
    
    create_user(name, email, password, phone)