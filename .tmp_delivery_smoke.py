from delivery.database import create_db_and_tables, engine
from delivery.delivery_service import DeliveryService
from sqlmodel import Session

create_db_and_tables()
with Session(engine) as db:
    service = DeliveryService(db)
    points = service.get_pickup_points(provider='dpd', country_code='LV', limit=10)
    print('DPD_POINTS', len(points))
    if points:
        p = points[0]
        print('FIRST', p.system_point_id, p.name, p.city)
        resolved = service.resolve_pickup_point(provider='dpd', system_point_id=p.system_point_id)
        print('RESOLVED', bool(resolved))
print('OK')
