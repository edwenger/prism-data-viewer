"""
PRISM Data Processing

This script loads and processes the PRISM and PRISM2 cohort data, creating cleaned
CSV files that can be used for visualization.

PRISM (2011-2017): 3 sites - Nagongera, Walukuba, Kihihi
PRISM2 (2017-2019): Single site continuation (Nagongera area)
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


def process_prism2_data(data_dir='data', output_dir='data'):
    """
    Load and process PRISM2 data files, creating a comprehensive cleaned dataset.

    PRISM2 is a single-site continuation study (2017-2019) with enhanced molecular
    data including qPCR, complexity of infection, and haplotype information.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing raw PRISM2 data files
    output_dir : str or Path
        Directory where cleaned CSV file will be saved
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

    print("=" * 80)
    print("LOADING PRISM2 DATA FILES")
    print("=" * 80)

    # Load the main data files
    print("\n1. Loading Households...")
    households = pd.read_csv(
        data_dir / 'PRISM2_cohort_Households.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {households.shape}")
    print(f"   Households: {households['Household_Id'].nunique()}")

    print("\n2. Loading Participants...")
    participants = pd.read_csv(
        data_dir / 'PRISM2_cohort_Participants.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {participants.shape}")

    print("\n3. Loading Participant Repeated Measures...")
    repeated_measures = pd.read_csv(
        data_dir / 'PRISM2_cohort_Participant_repeated_measures.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {repeated_measures.shape}")

    print("\n4. Loading Samples...")
    samples = pd.read_csv(
        data_dir / 'PRISM2_cohort_Samples.txt',
        sep='\t',
        low_memory=False
    )
    print(f"   Shape: {samples.shape}")

    print("\n" + "=" * 80)
    print("PROCESSING PRISM2 DATA")
    print("=" * 80)

    print(f"\nTotal households: {households['Household_Id'].nunique()}")
    print(f"Total participants: {participants['Participant_Id'].nunique()}")
    print(f"Total observations: {repeated_measures.shape[0]}")
    print(f"Total samples: {samples.shape[0]}")

    # Merge datasets
    # Start with repeated measures and add participant info
    df = repeated_measures.merge(
        participants[['Participant_Id', 'Sex [PATO_0000047]',
                      'Enrollment date [EUPATH_0000151]',
                      'Participant enrolled in PRISM1 [EUPATH_0010424]']],
        on='Participant_Id',
        how='left'
    )

    # Add household info
    df = df.merge(
        households[['Household_Id',
                    'Household wealth index, categorical [EUPATH_0000143]',
                    'Household status in PRISM1 [EUPATH_0020101]']],
        on='Household_Id',
        how='left'
    )

    # Add sample data - this is where the rich molecular data lives
    sample_cols = [
        'Participant_repeated_measure_Id',
        # Microscopy
        'Plasmodium asexual stages, by microscopy [EUPATH_0000048]',
        'Plasmodium asexual stages, by microscopy result (/uL) [EUPATH_0000092]',
        'Plasmodium gametocytes, by microscopy [EUPATH_0000207]',
        'Plasmodium gametocytes, by microscopy result (/uL) [EUPATH_0023018]',
        'Hemoglobin (g/dL) [CMO_0000026]',
        # qPCR detection and density
        'Plasmodium, by qPCR [EUPATH_0025125]',
        'Plasmodium, by qPCR result (/uL) [EUPATH_0020166]',
        'Plasmodium density categorization, by qPCR [EUPATH_0020248]',
        # Gametocytes by qPCR
        'Plasmodium gametocytes, by qPCR [EUPATH_0022172]',
        'Plasmodium gametocytes, by qPCR result (/uL) [EUPATH_0020195]',
        'Plasmodium female gametocytes, by qPCR result (/uL) [EUPATH_0020194]',
        'Plasmodium male gametocytes, by qPCR result (/uL) [EUPATH_0020193]',
        # Complexity of infection and haplotypes
        'Plasmodium complexity of infection [EUPATH_0020245]',
        'Plasmodium haplotype ID [EUPATH_0020246]',
        # Species
        'Plasmodium species, by qPCR [OBI_0003044]',
        'Plasmodium falciparum [EUPATH_0021028]',
        'Plasmodium malariae [EUPATH_0021030]',
        'Plasmodium ovale [EUPATH_0020167]',
        'Plasmodium vivax [EUPATH_0021029]',
        # Mosquito feeding assay (infectivity)
        'Membrane feeding performed [EUPATH_0020240]',
        'Mosquitoes with oocysts count [EUPATH_0020242]',
        'Mosquitoes with oocysts proportion [EUPATH_0020243]',
        'Mosquitoes dissected count [EUPATH_0020120]',
        'Plasmodium oocyst complexity of infection [EUPATH_0020241]',
    ]

    # Only include columns that exist in the samples dataframe
    sample_cols = [col for col in sample_cols if col in samples.columns]

    # Inner join to only keep observations with sample data
    df = df.merge(
        samples[sample_cols],
        on='Participant_repeated_measure_Id',
        how='inner'
    )

    # Rename columns to simpler names
    column_mapping = {
        # Core identifiers and demographics
        'Observation date [EUPATH_0004991]': 'date',
        'Participant_Id': 'id',
        'Sex [PATO_0000047]': 'gender',
        'Enrollment date [EUPATH_0000151]': 'enrollment_date',
        'Participant enrolled in PRISM1 [EUPATH_0010424]': 'enrolled_prism1',
        'Age (years) [OBI_0001169]': 'age',
        'Age group [EUPATH_0010367]': 'age_group',
        # Clinical
        'Temperature (C) [OBI_0003073]': 'temperature',
        'Febrile [EUPATH_0000097]': 'fever',
        'Observation type [BFO_0000015]': 'visittype',
        'Hemoglobin (g/dL) [CMO_0000026]': 'hemoglobin',
        'Malaria diagnosis [EUPATH_0000090]': 'malaria_diagnosis',
        'Antimalarial medication [EUPATH_0000058]': 'antimalarial',
        'ITN last night [EUPATH_0000216]': 'itn_lastnight',
        # Household
        'Household wealth index, categorical [EUPATH_0000143]': 'wealth_index',
        'Household status in PRISM1 [EUPATH_0020101]': 'household_prism1',
        # Microscopy
        'Plasmodium asexual stages, by microscopy [EUPATH_0000048]': 'microscopy_positive',
        'Plasmodium asexual stages, by microscopy result (/uL) [EUPATH_0000092]': 'parasitedensity',
        'Plasmodium gametocytes, by microscopy [EUPATH_0000207]': 'gametocytes',
        'Plasmodium gametocytes, by microscopy result (/uL) [EUPATH_0023018]': 'gametocyte_density',
        # qPCR
        'Plasmodium, by qPCR [EUPATH_0025125]': 'qpcr_positive',
        'Plasmodium, by qPCR result (/uL) [EUPATH_0020166]': 'qpcr_density',
        'Plasmodium density categorization, by qPCR [EUPATH_0020248]': 'qpcr_density_cat',
        # Gametocytes by qPCR
        'Plasmodium gametocytes, by qPCR [EUPATH_0022172]': 'gametocytes_qpcr',
        'Plasmodium gametocytes, by qPCR result (/uL) [EUPATH_0020195]': 'gametocytes_qpcr_density',
        'Plasmodium female gametocytes, by qPCR result (/uL) [EUPATH_0020194]': 'gametocytes_female_density',
        'Plasmodium male gametocytes, by qPCR result (/uL) [EUPATH_0020193]': 'gametocytes_male_density',
        # Complexity and haplotypes
        'Plasmodium complexity of infection [EUPATH_0020245]': 'coi',
        'Plasmodium haplotype ID [EUPATH_0020246]': 'haplotype_id',
        # Species
        'Plasmodium species, by qPCR [OBI_0003044]': 'species_qpcr',
        'Plasmodium falciparum [EUPATH_0021028]': 'pf_positive',
        'Plasmodium malariae [EUPATH_0021030]': 'pm_positive',
        'Plasmodium ovale [EUPATH_0020167]': 'po_positive',
        'Plasmodium vivax [EUPATH_0021029]': 'pv_positive',
        # Mosquito feeding
        'Membrane feeding performed [EUPATH_0020240]': 'membrane_feeding',
        'Mosquitoes with oocysts count [EUPATH_0020242]': 'mosquitoes_oocyst_positive',
        'Mosquitoes with oocysts proportion [EUPATH_0020243]': 'oocyst_prevalence',
        'Mosquitoes dissected count [EUPATH_0020120]': 'mosquitoes_dissected',
        'Plasmodium oocyst complexity of infection [EUPATH_0020241]': 'oocyst_coi',
    }

    df = df.rename(columns=column_mapping)

    # Select relevant columns (only those that exist after renaming)
    relevant_cols = [
        # Core
        'date', 'id', 'Household_Id', 'age', 'age_group', 'gender',
        'enrollment_date', 'enrolled_prism1', 'household_prism1', 'wealth_index',
        # Clinical
        'temperature', 'fever', 'visittype', 'hemoglobin',
        'malaria_diagnosis', 'antimalarial', 'itn_lastnight',
        # Microscopy
        'microscopy_positive', 'parasitedensity', 'gametocytes', 'gametocyte_density',
        # qPCR
        'qpcr_positive', 'qpcr_density', 'qpcr_density_cat',
        # Gametocytes qPCR
        'gametocytes_qpcr', 'gametocytes_qpcr_density',
        'gametocytes_female_density', 'gametocytes_male_density',
        # Molecular
        'coi', 'haplotype_id',
        # Species
        'species_qpcr', 'pf_positive', 'pm_positive', 'po_positive', 'pv_positive',
        # Infectivity
        'membrane_feeding', 'mosquitoes_dissected',
        'mosquitoes_oocyst_positive', 'oocyst_prevalence', 'oocyst_coi',
    ]

    relevant_cols = [col for col in relevant_cols if col in df.columns]
    df_clean = df[relevant_cols].copy()

    # Convert date column
    df_clean['date'] = pd.to_datetime(df_clean['date'])

    # Print summary statistics
    print(f"\n  Date range: {df_clean['date'].min().date()} to {df_clean['date'].max().date()}")

    obs_per_participant = df_clean.groupby('id').size()
    print(f"  Observations per participant: mean={obs_per_participant.mean():.1f}, median={obs_per_participant.median():.1f}")

    # Microscopy prevalence
    microscopy_pos = df_clean[df_clean['parasitedensity'] > 0]
    if len(microscopy_pos) > 0:
        prevalence = 100 * len(microscopy_pos) / len(df_clean[df_clean['parasitedensity'].notna()])
        print(f"  Microscopy prevalence: {prevalence:.2f}%")
        print(f"  Positive density: mean={microscopy_pos['parasitedensity'].mean():.0f}, median={microscopy_pos['parasitedensity'].median():.0f} parasites/µL")

    # qPCR prevalence
    qpcr_tested = df_clean[df_clean['qpcr_positive'].isin(['Positive', 'Negative'])]
    if len(qpcr_tested) > 0:
        qpcr_pos = qpcr_tested[qpcr_tested['qpcr_positive'] == 'Positive']
        qpcr_prevalence = 100 * len(qpcr_pos) / len(qpcr_tested)
        print(f"  qPCR prevalence: {qpcr_prevalence:.2f}% (n={len(qpcr_tested)} tested)")

    # COI summary
    coi_data = df_clean[df_clean['coi'].notna() & (df_clean['coi'] != '')]
    if len(coi_data) > 0:
        coi_numeric = pd.to_numeric(coi_data['coi'], errors='coerce')
        print(f"  COI: mean={coi_numeric.mean():.2f}, max={coi_numeric.max():.0f} (n={len(coi_data)} samples)")

    # Save output file
    output_file = output_dir / 'prism2_cleaned.csv'
    df_clean.to_csv(output_file, index=False)
    print(f"\n  Saved: {output_file}")
    print(f"  Shape: {df_clean.shape}")

    print("\n" + "=" * 80)
    print("PRISM2 PROCESSING COMPLETE")
    print("=" * 80)

    return df_clean


if __name__ == '__main__':
    process_prism_data()
    print("\n\n")
    process_prism2_data()
