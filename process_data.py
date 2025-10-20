"""
PRISM Data Processing

This script loads and processes the PRISM cohort data, creating cleaned CSV files
for each site that can be used for visualization.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def process_prism_data(data_dir='data', output_dir='data'):
    """
    Load and process PRISM data files, creating site-specific cleaned datasets.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing raw PRISM data files
    output_dir : str or Path
        Directory where cleaned CSV files will be saved
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

    print("=" * 80)
    print("LOADING PRISM DATA FILES")
    print("=" * 80)

    # Load the main data files
    print("\n1. Loading Households...")
    households = pd.read_csv(
        data_dir / 'PRISM_cohort_Households.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {households.shape}")
    print(f"   Sub-counties: {households['Sub-county in Uganda [EUPATH_0000054]'].value_counts().to_dict()}")

    print("\n2. Loading Participants...")
    participants = pd.read_csv(
        data_dir / 'PRISM_cohort_Participants.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {participants.shape}")

    print("\n3. Loading Participant Repeated Measures...")
    repeated_measures = pd.read_csv(
        data_dir / 'PRISM_cohort_Participant_repeated_measures.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {repeated_measures.shape}")

    print("\n4. Loading Samples...")
    samples = pd.read_csv(
        data_dir / 'PRISM_cohort_Samples.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {samples.shape}")

    print("\n" + "=" * 80)
    print("PROCESSING DATA BY SITE")
    print("=" * 80)

    # Define sites and their transmission characteristics
    SITES = {
        'Nagongera': 'high transmission (Tororo district)',
        'Walukuba': 'medium transmission (Jinja district)',
        'Kihihi': 'low transmission (Kanungu district)'
    }

    print(f"\nTotal households across all sites: {households['Household_Id'].nunique()}")
    print(f"Total participants across all sites: {participants['Participant_Id'].nunique()}")
    print(f"Total observations across all sites: {repeated_measures.shape[0]}")

    # Store all original data with merged household info before site filtering
    participants_all = participants.merge(
        households[['Household_Id', 'Sub-county in Uganda [EUPATH_0000054]']],
        on='Household_Id',
        how='left'
    )

    # Process each site separately
    for site_name, site_description in SITES.items():
        print("\n" + "=" * 80)
        print(f"PROCESSING {site_name.upper()} - {site_description}")
        print("=" * 80)

        # Filter to current site
        site_households = households[
            households['Sub-county in Uganda [EUPATH_0000054]'] == site_name
        ]['Household_Id'].unique()

        site_participants = participants_all[
            participants_all['Household_Id'].isin(site_households)
        ].copy()

        site_repeated_measures = repeated_measures[
            repeated_measures['Participant_Id'].isin(site_participants['Participant_Id'])
        ].copy()

        site_samples = samples[
            samples['Participant_repeated_measure_Id'].isin(site_repeated_measures['Participant_repeated_measure_Id'])
        ].copy()

        print(f"\n{site_name} statistics:")
        print(f"  Households: {len(site_households)}")
        print(f"  Participants: {site_participants['Participant_Id'].nunique()}")
        print(f"  Observations: {site_repeated_measures.shape[0]}")
        print(f"  Samples: {site_samples.shape[0]}")

        # Merge datasets for this site
        df = site_repeated_measures.merge(
            site_participants[['Participant_Id', 'Sex [PATO_0000047]',
                              'Age at enrollment (years) [EUPATH_0000120]',
                              'Enrollment date [EUPATH_0000151]']],
            on='Participant_Id',
            how='left'
        )

        df = df.merge(
            site_samples[['Participant_repeated_measure_Id',
                         'Plasmodium asexual stages, by microscopy result (/uL) [EUPATH_0000092]',
                         'Plasmodium gametocytes, by microscopy [EUPATH_0000207]',
                         'Plasmodium, by LAMP [EUPATH_0000487]',
                         'Hemoglobin (g/dL) [EUPATH_0000047]']],
            on='Participant_repeated_measure_Id',
            how='left'
        )

        # Rename columns to simpler names
        column_mapping = {
            'Observation date [EUPATH_0004991]': 'date',
            'Participant_Id': 'id',
            'Sex [PATO_0000047]': 'gender',
            'Age at enrollment (years) [EUPATH_0000120]': 'age_at_enrollment',
            'Enrollment date [EUPATH_0000151]': 'enrollment_date',
            'Age (years) [OBI_0001169]': 'age',
            'Temperature (C) [EUPATH_0000110]': 'temperature',
            'Febrile [EUPATH_0000097]': 'fever',
            'Plasmodium asexual stages, by microscopy result (/uL) [EUPATH_0000092]': 'parasitedensity',
            'Plasmodium gametocytes, by microscopy [EUPATH_0000207]': 'gametocytes',
            'Plasmodium, by LAMP [EUPATH_0000487]': 'LAMP',
            'Observation type [BFO_0000015]': 'visittype',
            'Hemoglobin (g/dL) [EUPATH_0000047]': 'hemoglobin',
            'Malaria diagnosis [EUPATH_0000090]': 'malaria_diagnosis',
            'Antimalarial medication [EUPATH_0000058]': 'antimalarial',
        }

        df = df.rename(columns=column_mapping)

        # Select relevant columns
        relevant_cols = ['date', 'id', 'Household_Id', 'age', 'age_at_enrollment', 'gender',
                         'temperature', 'fever', 'parasitedensity', 'gametocytes', 'LAMP',
                         'visittype', 'hemoglobin', 'malaria_diagnosis', 'antimalarial']

        relevant_cols = [col for col in relevant_cols if col in df.columns]
        df_clean = df[relevant_cols].copy()

        # Convert date column
        df_clean['date'] = pd.to_datetime(df_clean['date'])

        # Print summary statistics
        print(f"\n  Date range: {df_clean['date'].min().date()} to {df_clean['date'].max().date()}")

        obs_per_participant = df_clean.groupby('id').size()
        print(f"  Observations per participant: mean={obs_per_participant.mean():.1f}, median={obs_per_participant.median():.1f}")

        parasite_pos = df_clean[df_clean['parasitedensity'] > 0]['parasitedensity']
        if len(parasite_pos) > 0:
            prevalence = 100 * len(parasite_pos) / len(df_clean)
            print(f"  Microscopy prevalence: {prevalence:.2f}%")
            print(f"  Positive density: mean={parasite_pos.mean():.0f}, median={parasite_pos.median():.0f} parasites/µL")
        else:
            print(f"  Microscopy prevalence: 0.00%")

        # Save site-specific file
        output_file = output_dir / f'prism_cleaned_{site_name.lower()}.csv'
        df_clean.to_csv(output_file, index=False)
        print(f"\n  Saved: {output_file}")

    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    process_prism_data()
