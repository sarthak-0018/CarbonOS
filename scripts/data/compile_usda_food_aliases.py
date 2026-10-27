"""Compile conservative product-name aliases from USDA FoodData Central Foundation Foods.

USDA names improve recognition only; they do not supply GHG factors or receipt mass.
The resulting aliases are grouped into CarbonOS's existing broad OWID food factors.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/food_vocabulary/usda-foundation-foods-2026-04.zip"
OUTPUT = ROOT / "backend/app/data/usda_food_aliases.json"
CORE_ALIASES = ROOT / "backend/app/data/product_aliases.json"
USDA_FOLDER = "FoodData_Central_foundation_food_csv_2026-04-30/"

EXCLUDE = re.compile(
    r"\b(juice|sauce|soup|broth|canned|pickled|dried|dehydrated|powder|"
    r"flour|starch|noodle|pasta|bread|cracker|cereal|chip|snack|candy|"
    r"sweetened|syrup|puree|paste|baby food|infant|formula|hummus|tempeh|"
    r"soy sauce|yogurt|yoghurt|butter|cream|ice cream|cooked|boiled|fried|"
    r"roasted|baked|grilled|smoked|breaded|seasoned|prepared|meal|recipe)\b",
    re.I,
)
AMBIGUOUS_CORE = {"beans", "meat", "fish", "fruit", "vegetables", "vegetable", "nuts", "grain"}


def map_factor(description: str, group: str) -> str | None:
    text = re.sub(r"\([^)]*\)", " ", description.casefold())
    text = re.sub(r"\s+", " ", text).strip()
    # These OWID categories describe unprocessed food groups. Processed forms and
    # foods whose production system materially changes the factor stay unmatched.
    if EXCLUDE.search(text):
        return None
    if group == "Fruits and Fruit Juices":
        if re.search(r"\b(apple|apples)\b", text): return "apples"
        if re.search(r"\b(banana|bananas|plantain)\b", text): return "bananas"
        if re.search(r"\b(orange|lemon|lime|grapefruit|tangerine|clementine|citrus)\b", text): return "citrus_fruit"
        if re.search(r"\b(berry|berries|grape|grapes|blueberry|strawberry|raspberry|blackberry|cranberry)\b", text): return "berries_grapes"
        return "other_fruit"
    if group == "Vegetables and Vegetable Products":
        if re.search(r"\b(tomato|tomatoes)\b", text): return "tomatoes"
        if re.search(r"\b(onion|onions|leek|leeks|shallot|scallion|green onion)\b", text): return "onions_leeks"
        if re.search(r"\b(potato|potatoes)\b", text): return "potatoes"
        if re.search(r"\b(carrot|carrots|beetroot|beet root|radish|turnip|parsnip|rutabaga|yam)\b", text): return "root_vegetables"
        if re.search(r"\b(cabbage|cauliflower|broccoli|brussels sprout|kale|bok choy|collard)\b", text): return "brassicas"
        return "other_vegetables"
    if group == "Legumes and Legume Products":
        if re.search(r"\b(peanut|peanuts|groundnut|groundnuts)\b", text): return "groundnuts"
        if re.search(r"\b(green pea|peas)\b", text): return "peas"
        if re.search(r"\b(soy milk|soya milk)\b", text): return "soy_milk"
        if re.search(r"\b(tofu)\b", text): return "tofu"
        if re.search(r"\b(bean|beans|lentil|lentils|chickpea|chickpeas|pulse|pulses|pea|peas|soybean|soybeans|edamame)\b", text): return "other_pulses"
        return None
    if group == "Dairy and Egg Products":
        if re.search(r"\b(soy|soya)\s+milk\b", text): return "soy_milk"
        if re.search(r"\b(chocolate|flavored|flavoured|sweetened|fermented|cultured)\b", text): return None
        if re.search(r"\b(egg|eggs)\b", text): return "eggs"
        if re.search(r"\b(cheese|paneer)\b", text): return "cheese"
        if re.search(r"\b(milk)\b", text): return "milk"
        return None
    if group == "Cereal Grains and Pasta":
        if re.search(r"\b(rice)\b", text): return "rice"
        if re.search(r"\b(oat|oats|oatmeal)\b", text): return "oatmeal"
        if re.search(r"\b(barley)\b", text): return "barley"
        if re.search(r"\b(maize|corn)\b", text): return "maize"
        if re.search(r"\b(wheat|rye)\b", text): return "wheat_rye"
        return None
    if group == "Nut and Seed Products":
        if re.search(r"\b(peanut|peanuts|groundnut|groundnuts)\b", text): return "groundnuts"
        if re.search(r"\b(almond|almonds|cashew|cashews|walnut|walnuts|pecan|pistachio|hazelnut|macadamia|brazil nut)\b", text): return "nuts"
        return None
    if group == "Poultry Products" and re.search(r"\b(chicken|turkey|duck)\b", text): return "poultry_meat"
    if group == "Pork Products" and re.search(r"\b(pork|pig)\b", text): return "pig_meat"
    if group == "Lamb, Veal, and Game Products" and re.search(r"\b(lamb|mutton)\b", text): return "lamb_mutton"
    # Beef-herd and dairy-herd factors differ substantially; generic beef names
    # cannot safely choose between them. Generic fish/prawns cannot establish farmed.
    if group == "Finfish and Shellfish Products" and re.search(r"\b(farmed|aquaculture|aquacultured)\b", text):
        if re.search(r"\b(prawn|prawns|shrimp|shrimps)\b", text): return "prawns_farmed"
        return "fish_farmed"
    return None


def clean_alias(value: str) -> str:
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.-")
    return value.casefold()


def normalized_alias(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("×", " x ")
    value = re.sub(r"(?<=\d)\s+(?=kg\b|gm?\b|ml\b|ltr\b)", "", value)
    value = re.sub(r"[^\w.]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing source archive: {SOURCE}")
    with zipfile.ZipFile(SOURCE) as archive:
        food_file = archive.open(USDA_FOLDER + "food.csv")
        category_file = archive.open(USDA_FOLDER + "food_category.csv")
        with io.TextIOWrapper(category_file, encoding="utf-8-sig", newline="") as stream:
            groups = {row["id"]: row["description"] for row in csv.DictReader(stream)}
        aliases: dict[str, set[str]] = defaultdict(set)
        descriptions_seen: set[str] = set()
        with io.TextIOWrapper(food_file, encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["data_type"] not in {"foundation_food", "sample_food", "market_acquisition"}:
                    continue
                description = re.sub(r"\s+", " ", row["description"]).strip()
                identity = description.casefold()
                if identity in descriptions_seen:
                    continue
                descriptions_seen.add(identity)
                group = groups.get(row["food_category_id"], "")
                factor = map_factor(description, group)
                if not factor:
                    continue
                # Keep the source's complete description and its leading food name.
                # Core terms are what most receipts actually print; full descriptions
                # preserve a traceable route for OCR that captures extra detail.
                aliases[factor].add(clean_alias(description))
                core = clean_alias(description.split(",", 1)[0])
                if core and len(core) >= 3 and core not in AMBIGUOUS_CORE:
                    aliases[factor].add(core)

    OUTPUT.write_text(json.dumps({key: sorted(values) for key, values in sorted(aliases.items())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(map(len, aliases.values()))
    normalized_names = {normalized_alias(alias) for values in aliases.values() for alias in values}
    core_data = json.loads(CORE_ALIASES.read_text(encoding="utf-8"))
    core_names = {normalized_alias(alias) for values in core_data.values() for alias in values}
    new_names = normalized_names - core_names
    print(f"Wrote {total} aliases ({len(normalized_names)} unique normalized names; {len(new_names)} new beyond curated aliases) across {len(aliases)} factor groups from {len(descriptions_seen)} unique USDA descriptions")
    if len(new_names) < 500:
        raise SystemExit("Fewer than 500 aliases survived conservative category mapping; no count claim is valid")


if __name__ == "__main__":
    main()
