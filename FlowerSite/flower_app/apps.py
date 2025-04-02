from django.apps import AppConfig

class FlowerAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flower_app'
    models_ready = False  # Добавляем инициализацию атрибута

    def ready(self):
        # Проверяем, что модели загружены только один раз
        if not self.models_ready:
            self.models_ready = True
            from . import signals  # noqa