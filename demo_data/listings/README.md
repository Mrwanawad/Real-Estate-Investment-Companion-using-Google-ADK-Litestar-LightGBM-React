# Real listings inventory

`developers.csv`, `projects.csv`, `units.csv` and `payment_plans.csv` are derived from
**"Egyptian Real Estate Listings"** by hassankhaled21 on Kaggle
(https://www.kaggle.com/datasets/hassankhaled21/egyptian-real-estate-listings): about 20,000
for-sale listings collected from PropertyFinder Egypt in August 2025, licensed
**CC BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/).

These derived files are shared under the same licence, CC BY-SA 4.0. They are not covered by
the repository's MIT licence, which applies to the code.

Regenerate them with `python scripts/import_listings.py` (downloads the dataset, no account
needed) or `--csv PATH` for a local copy.

## What changed from the source

- Kept: 16,112 of 19,924 listings, the residential types in the 12 areas the market models
  cover. Dropped: other areas (Hurghada, Alexandria, Shorouk, ...), land and palaces,
  duplicate listing ids, and implausible rows (price outside 0.5M-300M EGP, size outside
  25-2,000 m², or price per m² outside 5k-600k EGP).
- A compound (the first part of the location) becomes a project; each unit keeps its listing
  URL as `source_url` and its listing id as the code (`PF-<id>`).
- Types: Penthouse and Hotel Apartment become `apartment`, iVilla `villa`, Cabin `chalet`.

## Assumptions (fields the listings don't carry)

| Field | Rule |
| --- | --- |
| Developer | Not listed. One `DNL` "Developer not listed" record, tier B and a 75% on-time rate, so scoring stays neutral. The app hides the tier for these units |
| Installment plans | Per compound, up to three distinct terms from its installment listings: down payment = listed down payment / price, else a parsed "% down", else 10%; years parsed from the text, else 7; quarterly |
| Cash | Compounds with cash listings get a `Cash` plan (100% down) |
| Delivery year | Parsed from "delivery 20xx" in the text, else ready (2025) |
| Finishing | "fully finished" / "core & shell" in the text, else semi-finished |
| Floor, garden | Parsed from the text, else floor 1 (0 for villas and houses) and no garden |
| Maintenance deposit | 8% of price |

Rents stay synthetic. When seeding these listings, `scripts/seed.py` scales the synthetic
rents per area by the ratio of real to synthetic median price per m², so rental yields keep
each area's assumed yield.
