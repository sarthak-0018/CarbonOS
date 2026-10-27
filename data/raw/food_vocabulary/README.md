# USDA food-name vocabulary

`usda-foundation-foods-2026-04.zip` is the official USDA FoodData Central Foundation Foods CSV release dated April 30, 2026, downloaded from the [USDA FoodData Central dataset page](https://fdc.nal.usda.gov/download-datasets/). SHA-256: `70457EE9D9342F43BDA2010318C85F04210C689FDEB9CD2DA4C513B0E8DBC655`. The compiled `backend/app/data/usda_food_aliases.json` contains 2,077 distinct names after CarbonOS normalization, of which 2,041 are new beyond the curated aliases, drawn from 4,941 unique USDA Foundation Foods, sample-food, and market-acquisition descriptions.

The compiler maps only descriptions that can be conservatively assigned to an existing broad food factor. It deliberately excludes product groups without a compatible factor and ambiguous beef/farmed-seafood descriptions. USDA supplies the food-name/category vocabulary here; it does not supply the carbon factors used by CarbonOS. Alias matches use a broad category average and do not establish the product's origin, recipe, or exact life-cycle impact. The USDA release is U.S.-oriented and may not include Indian market names.

Rebuild the derived alias catalog with:

```powershell
python scripts/data/compile_usda_food_aliases.py
```

Do not derive receipt weight from the USDA food name. Carbon estimates still require a printed mass quantity or a printed package size that can be combined with the receipt's pack count.
