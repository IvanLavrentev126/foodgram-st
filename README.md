# Foodgram - Продуктовый помощник
## Описание проекта
Foodgram - это веб-приложение, которое позволяет пользователям:

- Публиковать рецепты
- Подписываться на других пользователей
- Добавлять рецепты в избранное
- Создавать списки покупок для выбранных рецептов
- Скачивать список покупок в формате PDF

## Используемые технологии
### Бэкенд:
- Python 3.9
- Django 3.2
- Django REST Framework
- PostgreSQL
- Nginx
- Gunicorn
- Docker

### Фронтенд:
- React

## Локальный запуск проекта
- Клонируйте репозиторий:

```bash
git clone https://github.com/IvanLavrentev126/foodgram-st.git
cd foodgram-st
```
- Перейдите в директорию backend и переименуйте `env.example -> .env.example`:

- Перейдите в директорию infra и запустите контейнеры:
```bash
cd infra
docker-compose up --build
```
- После успешного запуска:

-- Фронтенд будет доступен по адресу: http://localhost

-- API документация (OpenAPI/Swagger) будет доступна по адресу: http://localhost/api/docs/

-- API сервер будет доступен по адресу: http://127.0.0.1:8000/

## Настройка окружения
Пример содержимого файла .env (должен быть размещен в директории infra):

```
SECRET_KEY=your-secret-key-here
DEBUG=true
```

## Миграции

Миграции применяются автоматически при запуске контейнеров. Если нужно выполнить их вручную:

```bash
docker-compose exec backend python manage.py migrate
```
## Создание тестового пользователя
Для создания суперпользователя (администратора):

```bash
docker-compose exec backend python manage.py createsuperuser
```

Следуйте инструкциям в терминале для ввода email и пароля.