"""Generate bundled common weak passwords list for CivicLens."""

from pathlib import Path

BASE_WORDS = [
    "password", "civiclens", "admin", "administrator", "root", "guest", "secret", "default",
    "welcome", "changeme", "qwerty", "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "chennai", "tamilnadu", "india", "governor", "collector", "official", "government",
    "portal", "services", "scheme", "magalir", "urimai", "thittam", "smartcard", "rationcard",
    "access", "account", "freedom", "football", "baseball", "basketball", "monkey", "dragon",
    "master", "superman", "batman", "pokemon", "starwars", "sunshine", "princess", "shadow",
    "michael", "jessica", "william", "matthew", "anthony", "daniel", "david", "andrew",
    "computer", "internet", "security", "database", "network", "server", "system", "manager",
    "support", "service", "testing", "operator", "control", "finance", "office", "company",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "summer", "winter", "spring", "autumn", "morning", "evening",
    "iloveyou", "trustnoone", "letmein", "openup", "opensesame", "cannotguess", "hardtopass",
    "correcthorse", "batterystaple", "onetwothree", "fourfivesix", "password1234",
]

SUFFIXES = [
    "", "1", "12", "123", "1234", "12345", "123456", "2020", "2021", "2022", "2023", "2024",
    "2025", "2026", "!", "@", "#", "$", "!@#", "@123", "!123", "123!", "123@", "321", "007",
    "999", "111", "000"
]

PREFIXES = ["", "the", "my", "super", "secret", "new"]

def generate_passwords():
    passwords = set()
    
    # Common sequences
    for i in range(1, 10):
        passwords.add(str(i) * 12)
        passwords.add(str(i) * 16)
    
    seqs = [
        "123456789012", "1234567890123", "098765432109", "112233445566",
        "qwertyuiopas", "asdfghjklzxc", "zxcvbnmasdfg", "qazwsxedcrfv",
        "1q2w3e4r5t6y", "1a2b3c4d5e6f", "abcdefghijkl", "zyxwvutsrqpo",
        "passwordpassword", "adminadminadmin", "welcome123456", "letmeinplease1",
    ]
    passwords.update(seqs)
    
    for bw in BASE_WORDS:
        passwords.add(bw)
        for s in SUFFIXES:
            passwords.add(f"{bw}{s}")
            passwords.add(f"{bw.capitalize()}{s}")
            passwords.add(f"{bw.upper()}{s}")
        for p in PREFIXES:
            if p:
                passwords.add(f"{p}{bw}")
                passwords.add(f"{p}{bw}123")
                passwords.add(f"{p}{bw}!")
                
    # Multi-word combinations
    for w1 in ["super", "admin", "secret", "civic", "master", "chennai", "smart", "gov"]:
        for w2 in ["password", "portal", "system", "service", "admin", "user", "access", "login"]:
            for s in ["", "123", "!", "@2024", "@2025", "@2026", "2024!"]:
                passwords.add(f"{w1}{w2}{s}")
                passwords.add(f"{w1}_{w2}{s}")
                passwords.add(f"{w1}.{w2}{s}")

    sorted_passwords = sorted(list(passwords))
    out_path = Path(__file__).resolve().parent.parent / "backend" / "app" / "auth" / "common_passwords.txt"
    out_path.write_text("\n".join(sorted_passwords), encoding="utf-8")
    print(f"Generated {len(sorted_passwords)} common passwords in {out_path}")

if __name__ == "__main__":
    generate_passwords()
