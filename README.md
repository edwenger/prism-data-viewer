# PRISM Household Malaria Viewer

Interactive web-based visualization of household-level malaria surveillance data from the PRISM (Program for Resistance, Immunology, Surveillance, and Modeling of Malaria) cohort study in Uganda.

**🌐 [View Live Interactive Visualization](https://edwenger.github.io/prism-data-viewer/)**

## Overview

This project provides an interactive, web-based viewer for exploring malaria infection patterns within households across three transmission intensity sites in Uganda:

- **Nagongera** - High transmission (Tororo district) - 105 households
- **Walukuba** - Medium transmission (Jinja district) - 99 households
- **Kihihi** - Low transmission (Kanungu district) - 101 households

The visualization displays longitudinal test results for all members of multi-person households, with each row representing one individual. Users can navigate between households using a dropdown menu, Previous/Next buttons, or arrow keys. Households are sorted by total number of microscopy-positive observations.

## Features

- **Interactive household navigation** - Dropdown menu, Previous/Next buttons, and arrow key support
- **Rich visualization** - Shows all visits, fever episodes, diagnostic test results, and parasite densities
- **Hover details** - Detailed information on demand for each data point
- **Multi-site support** - Separate visualizations for each transmission intensity site
- **Static hosting** - Pure HTML/JavaScript using Plotly, can be hosted on GitHub Pages

## Visualization Elements

Each individual's timeline shows:
- **All visits** - Small gray dots
- **Fever visits** - Red dots
- **Microscopy/LAMP negative** - Open circles
- **Parasite positive** - Colored/sized circles by density (log scale, yellow to red)
- **LAMP positive** - Light yellow circles (submicroscopic infections)
- **Gametocytes detected** - Olive ring around microscopy-positive results

## Project Structure

```
prism-data-viewer/
├── data/                          # Raw and processed data files
│   ├── PRISM_cohort_*.txt        # Original data from ClinEpiDB
│   ├── prism_cleaned_*.csv       # Processed site-specific data
│   └── DATA_ATTRIBUTION.md       # Data citation and attribution
├── docs/                          # Generated HTML files for GitHub Pages
│   ├── index.html                # Landing page with site selection
│   ├── nagongera.html            # Interactive viewer for Nagongera
│   ├── walukuba.html             # Interactive viewer for Walukuba
│   └── kihihi.html               # Interactive viewer for Kihihi
├── process_data.py               # Script to process raw PRISM data
├── generate_viewer.py            # Script to generate interactive HTML files
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Installation & Usage

### Requirements

```bash
pip install -r requirements.txt
```

### Process Raw Data

To regenerate the cleaned CSV files from the raw PRISM data:

```bash
python process_data.py
```

This creates `prism_cleaned_*.csv` files in the `data/` directory.

### Generate Interactive Viewers

To regenerate the HTML visualization files:

```bash
python generate_viewer.py
```

This creates/updates HTML files in the `docs/` directory.

## Data Attribution

**Dataset:** PRISM ICEMR Cohort
**Source:** ClinEpiDB (Dataset ID: DS_0ad509829e)
**Version:** Release 21 (2022-MAR-03)

**Citation:** Grant Dorsey, Moses Kamya, Bryan Greenhouse, et al. Dataset: PRISM ICEMR Cohort. ClinEpiDB. 03 March 2022, Release 21 (https://clinepidb.org/ce/app/workspace/analyses/DS_0ad509829e/new).

The PRISM cohort study was conducted as part of the East Africa International Center of Excellence for Malaria Research (ICEMR), supported by NIAID (U19AI089674).

**Data Access:** https://clinepidb.org/ce/app/record/dataset/DS_0ad509829e

### Terms of Use

Data accessed from ClinEpiDB is public and available without login. Users should cite the dataset using the citation provided above when publishing results derived from this data.

For questions about data use and permissions, please refer to the [ClinEpiDB website](https://clinepidb.org) or contact the PRISM study investigators.

## GitHub Pages Deployment

This project is configured for GitHub Pages deployment from the `docs/` directory:

1. Go to repository Settings → Pages
2. Set Source to "Deploy from a branch"
3. Select branch `main` and folder `/docs`
4. Save

The site will be available at: `https://[username].github.io/prism-data-viewer/`

## Technical Details

- **Visualization Library:** Plotly (Python) with HTML export
- **Data Processing:** pandas, numpy
- **Hosting:** Static HTML files (GitHub Pages compatible)
- **Navigation:** Custom JavaScript for keyboard and button controls
- **File Size:** ~1.1-2.4 MB per site (includes embedded data)

## Origin

This project is a refactored, web-friendly version of static visualizations originally developed by Edward Wenger at IDM.

## License

The visualization code in this repository is provided as-is for research and educational purposes. The underlying PRISM data is subject to ClinEpiDB terms of use as described in the Data Attribution section above.
