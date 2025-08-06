import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from app.models import Recipe, Ingredient, RecipeIngredient
from faker import Faker
import random
from django.core.files import File
from io import BytesIO
from PIL import Image

CustomUser = get_user_model()
data_generator = Faker()


class Command(BaseCommand):
    help_text = "Generates sample data: users and their recipes"
    user_count = 5
    dish_count = 10

    def handle(self, *args, **kwargs):
        self.stdout.write(f"Generating {self.user_count} sample users...")
        user_list = []
        for i in range(self.user_count):
            new_user = CustomUser.objects.create(
                email=data_generator.unique.email(),
                username=data_generator.unique.user_name(),
                first_name=data_generator.first_name(),
                last_name=data_generator.last_name(),
                password=data_generator.password(),
            )
            user_list.append(new_user)
            self.stdout.write(f"Added user: {new_user.email}")
        json_path = Path(__file__).parent.parent / 'fixtures' / 'ingredients.json'
        with open(json_path) as file:
            components = json.load(file)

        self.stdout.write("Preparing ingredients...")
        for item in components:
            name = item['name']
            measurement_unit = item['measurement_unit']
            obj, is_new = Ingredient.objects.get_or_create(
                name=name, defaults={"measurement_unit": measurement_unit}
            )
            if is_new:
                self.stdout.write(f"Added ingredient: {obj}")

        available_ingredients = list(Ingredient.objects.all())

        self.stdout.write(f"Creating {self.dish_count} dishes per user...")
        for account in user_list:
            for j in range(self.dish_count):
                img = Image.new(
                    "RGB",
                    (120, 120),
                    color=(
                        random.randrange(0, 256),
                        random.randrange(0, 256),
                        random.randrange(0, 256),
                    ),
                )
                img_buffer = BytesIO()
                img.save(img_buffer, format="JPEG")
                img_file = File(img_buffer, name=f"dish_{data_generator.unique.word()}.jpg")

                new_recipe = Recipe.objects.create(
                    author=account,
                    name=data_generator.sentence(nb_words=4),
                    image=img_file,
                    text="\n".join(data_generator.texts(nb_texts=3)),
                    cooking_time=random.randrange(5, 125),
                )

                selected_components = random.sample(
                    available_ingredients, random.randrange(3, 6)
                )
                for component in selected_components:
                    RecipeIngredient.objects.create(
                        recipe=new_recipe,
                        ingredient=component,
                        amount=random.randrange(50, 1000),
                    )

                self.stdout.write(f"Added dish: {new_recipe.name} by {account.email}")

        self.stdout.write(self.style.SUCCESS("Test data generation complete"))

