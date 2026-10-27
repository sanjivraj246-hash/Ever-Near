from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.parent import router as parent_router
from app.api.family import router as family_router
from app.api.checkins import router as checkins_router, alias_router as checkins_alias_router
from app.api.medications import router as medications_router
from app.api.alerts import router as alerts_router
from app.routers.care import router as care_router
from app.routers.privacy import router as privacy_router
from app.routers.health_docs import router as health_docs_router
from app.routers.notifications import router as notifications_router
from app.routers.support import router as support_router
from app.routers.ai import router as ai_router
from app.routers.cameras import router as cameras_router
from app.routers.safety import router as safety_router
from app.routers.sos import router as sos_router
from app.routers.communication import router as communication_router
from app.routers.family_connection import router as family_connection_router

api_router = APIRouter()

# 1. /auth
api_router.include_router(auth_router)

# 2. /parent
api_router.include_router(parent_router)

# 3. /family
api_router.include_router(family_router)

# 4. /checkins (with /check-ins backward-compatible alias)
api_router.include_router(checkins_router)
api_router.include_router(checkins_alias_router)

# 5. /medications
api_router.include_router(medications_router)

# 6. /alerts (with /sos alias)
api_router.include_router(alerts_router)
api_router.include_router(alerts_router, prefix="/sos", tags=["SOS Emergency Alias"])

# 7. /care
api_router.include_router(care_router)

# 8. /privacy
api_router.include_router(privacy_router)

# 9. /health-docs
api_router.include_router(health_docs_router)

# 10. /notifications
api_router.include_router(notifications_router)

# 11. /support (and root support routes)
api_router.include_router(support_router)
api_router.include_router(support_router, prefix="/support")

# 12. /ai
api_router.include_router(ai_router)

# 13. /cameras
api_router.include_router(cameras_router)

# 14. /safety
api_router.include_router(safety_router)

# 15. /sos
api_router.include_router(sos_router)

# 16. /communication
api_router.include_router(communication_router)

# 17. /family-connection
api_router.include_router(family_connection_router)

__all__ = ["api_router"]
