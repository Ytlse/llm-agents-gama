# 2. The 21-Variable Protocol and Information Parity

This chapter details the input feature contract governing the benchmark. We define the 21 variables that enforce strict informational parity between tabular models and generative agents.

## 2.1 The Informational Contract

Fair comparison between machine learning baselines and generative language models requires identical input information. The protocol contract (`spec_version 2`) designates 21 input features and forbids supplementary tabular predictors.

Supervised tabular models observe these 21 variables exclusively. In contrast, generative language models receive these identical variables embedded within narrative natural language prompts, accompanied by trip itinerary options and environmental context.

## 2.2 Complete Feature Dictionary

The 21 variables fall into three structural blocks. Table 2.1 provides the complete variable dictionary, including data types, modalities, and physical definitions.

*Table 2.1. The 21 variables of the comparison protocol.*

| Variable name | Data type | Categories / Modalities / Range | Description |
|---|---|---|---|
| `age` | Integer | $5 \dots 105$ years | Age in completed years |
| `gender` | Categorical | `female`, `male` | Legal gender of the persona |
| `household_size` | Integer | $1 \dots 12$ persons | Total individuals in household |
| `has_driving_license` | Boolean | True, False | Valid driving license held |
| `has_pt_subscription` | Boolean | True, False | Active public transit pass |
| `number_of_cars` | Integer | $0 \dots 6$ vehicles | Motor vehicles owned by household |
| `car_availability` | Categorical | `always`, `sometimes`, `never` | Frequency of car access |
| `has_bike` | Boolean | True, False | Working personal bicycle owned |
| `socioprofessional_class` | Categorical | 8 modalities (INSEE CS1–CS8) | Socioprofessional status |
| `main_occupation` | Categorical | 8 modalities | Primary daily occupation |
| `employed` | Boolean | True, False | Holds active employment |
| `studies` | Boolean | True, False | Enrolled in education |
| `purpose` | Categorical | `home`, `work`, `study`, `shopping`, `leisure`, `other` | Trip destination activity |
| `purpose_origin` | Categorical | Same 6 modalities | Trip origin activity |
| `departure_hour` | Numeric | $0.00 \dots 23.99$ hours | Planned trip departure time |
| `od_km` | Numeric | $0.05 \dots 85.00$ km | Straight-line Euclidean distance |
| `same_zone` | Boolean | True, False | Origin and destination in same zone |
| `dist_center_orig_km` | Numeric | $0.00 \dots 45.00$ km | Distance from origin to Capitole centroid |
| `dist_center_dest_km` | Numeric | $0.00 \dots 45.00$ km | Distance from destination to Capitole |
| `density_orig` | Numeric | $10 \dots 25\,000$ hab/km² | Gross population density at origin |
| `density_dest` | Numeric | $10 \dots 25\,000$ hab/km² | Gross population density at destination |

## 2.3 Spatial Coordinates and Projections

All geometric metrics use the official French Lambert-93 planar projection (EPSG:2154). We calculate the inner city reference distance relative to the geographic centroid of the historic Capitole sector in Toulouse.
