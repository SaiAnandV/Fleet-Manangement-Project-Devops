"""Load sample data:  python seed.py"""
from app import create_app

c = create_app().test_client()
if not c.get("/api/vehicles").json:
    d1 = c.post("/api/drivers", json={"name": "Ravi Kumar", "phone": "9876543210", "license_no": "DL-1001"}).json["id"]
    d2 = c.post("/api/drivers", json={"name": "Anita Rao", "phone": "9123456780", "license_no": "DL-1002"}).json["id"]
    v1 = c.post("/api/vehicles", json={"reg_number": "TS09AB1234", "make": "Tata", "model": "Ace", "year": 2021, "odometer": 42000, "driver_id": d1}).json["id"]
    v2 = c.post("/api/vehicles", json={"reg_number": "TS10CD5678", "make": "Mahindra", "model": "Bolero", "year": 2020, "odometer": 78000, "driver_id": d2}).json["id"]
    c.post("/api/maintenance", json={"vehicle_id": v1, "service_type": "Oil change", "service_date": "2026-01-15", "cost": 1800, "status": "Completed"})
    c.post("/api/maintenance", json={"vehicle_id": v2, "service_type": "Brake inspection", "service_date": "2026-10-20", "status": "Scheduled"})
    print("Sample data loaded")
