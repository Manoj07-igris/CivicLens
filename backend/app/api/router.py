from fastapi import APIRouter
from .health import router as health_router
from .auth import router as auth_router
from .gemini import router as gemini_router
from .chat import router as chat_router
from .documents import router as documents_router
from .agent import router as agent_router
from .comparison import router as comparison_router
from .sources import router as sources_router
from .verification import router as verification_router
from .portals import router as portals_router
from .services import router as services_router
from .grievances import router as grievances_router
from .browser import router as browser_router
from .conversations import router as conversations_router
from .preferences import router as preferences_router
from .activity import router as activity_router
from .system import router as system_router

api_router = APIRouter(prefix="/api/v1")

# Include domain routers
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(gemini_router)
api_router.include_router(chat_router)
api_router.include_router(documents_router)
api_router.include_router(agent_router)
api_router.include_router(comparison_router)
api_router.include_router(sources_router)
api_router.include_router(verification_router)
api_router.include_router(portals_router)
api_router.include_router(services_router)
api_router.include_router(grievances_router)
api_router.include_router(browser_router)
api_router.include_router(conversations_router)
api_router.include_router(preferences_router)
api_router.include_router(activity_router)
api_router.include_router(system_router)

