# 🏨 Hotel Staff Manager

Διαχείριση προσωπικού & βαρδιών για ξενοδοχεία.

## Γρήγορο Ξεκίνημα

```bash
# 1. Εγκατάσταση
pip install -r requirements.txt

# 2. Migrations
python manage.py makemigrations
python manage.py migrate

# 3. Superuser
python manage.py createsuperuser

# 4. Setup groups
python manage.py setup_groups

# 5. Run
python manage.py runserver