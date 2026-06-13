# Industries Barcode System

A Flask barcode inventory web app with user login, inventory scanning, and an administrator console.

## Default login details

The app creates an admin account on first startup when no account with `ADMIN_USERNAME` exists.

- **Admin URL:** `http://localhost:5000/admin`
- **Username:** `admin`
- **Password:** `admin12345`

Change these before production by setting `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`.
Also set a strong `SECRET_KEY`.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
SECRET_KEY=dev-secret ADMIN_PASSWORD=admin12345 python app.py
```

Open `http://localhost:5000`.

## Build and run with Docker on Debian, Ubuntu, or Windows Docker Desktop

```bash
docker build -t industries-barcode-system .
docker run --rm -p 5000:5000 \
  -e SECRET_KEY="replace-me" \
  -e ADMIN_USERNAME="admin" \
  -e ADMIN_EMAIL="admin@example.com" \
  -e ADMIN_PASSWORD="replace-this-password" \
  -v barcode-data:/data \
  industries-barcode-system
```

Or use Compose:

```bash
docker compose up --build
```

Persistent SQLite data is stored in the Docker volume mounted at `/data`.

## Admin console

Admins can visit `/admin` to view system totals, manage user admin access, delete users, and review recent inventory updates.
