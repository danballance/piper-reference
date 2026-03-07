from litestar import Litestar
from litestar.di import Provide
from litestar.logging import LoggingConfig

from api.todo.application.services import TodoService
from api.todo.infrastructure.memory_repo import InMemoryTodoRepository
from api.todo.presentation.controllers import TodoController


def create_app() -> Litestar:
    repository = InMemoryTodoRepository()
    service = TodoService(repository=repository)

    logging_config = LoggingConfig(
        root={"level": "DEBUG", "handlers": ["queue_listener"]},
        formatters={
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        log_exceptions="always",
    )

    return Litestar(
        route_handlers=[TodoController],
        dependencies={"service": Provide(lambda: service, sync_to_thread=False)},
        logging_config=logging_config,
    )


app = create_app()
