"""
Generate interactive household viewer HTML file

This script creates a standalone HTML file with an interactive household viewer
that can be hosted on GitHub Pages.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import colorsys
import json
from pathlib import Path


def generate_haplotype_color_map():
    colors = {}
    for i in range(51):
        hue = (i * 0.618033988749895) % 1.0
        sat = 0.9 if i % 2 == 0 else 0.55
        val = 0.85 if i % 3 != 2 else 0.65
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        colors[f'pfama1.{i:02d}'] = f'rgb({int(r*255)},{int(g*255)},{int(b*255)})'
    return colors


def create_interactive_viewer(site='nagongera', output_file='docs/index.html', is_prism2=False):
    """
    Create an interactive household viewer with dropdown navigation.

    Parameters
    ----------
    site : str
        Site name ('nagongera', 'walukuba', 'kihihi', or 'prism2')
    output_file : str or Path
        Output HTML file path
    is_prism2 : bool
        If True, load PRISM2 data and use qPCR instead of LAMP
    """

    trap_summary = None

    if is_prism2:
        print(f"Loading PRISM2 data...")
        df = pd.read_csv('data/prism2_cleaned.csv', parse_dates=['date'])
        # PRISM2 doesn't have age_at_enrollment, compute from first observation
        first_obs = df.groupby('id').first().reset_index()[['id', 'age']]
        first_obs = first_obs.rename(columns={'age': 'age_at_enrollment'})
        df = df.merge(first_obs, on='id', how='left')
        # Use qPCR positive column, create binary for submicroscopic detection
        df['molecular_positive'] = (df['qpcr_positive'] == 'Positive') | (df['qpcr_density'] > 0)
        df['molecular_tested'] = df['qpcr_positive'].isin(['Positive', 'Negative'])
        molecular_label = 'qPCR'

        # Load household entomology (light trap) data
        print("Loading PRISM2 light trap data...")
        trap_df = pd.read_csv('data/PRISM2_cohort_Household_repeated_measures.txt',
                              sep='\t', low_memory=False)
        trap_df = trap_df.rename(columns={
            'Collection date [EUPATH_0020003]': 'date',
            'Female Anopheles count [EUPATH_0000135]': 'female_anopheles',
            'Collection working [EUPATH_0020180]': 'working',
            'Anopheles dissected for parity count [EUPATH_0000194]': 'dissected_parity',
            'Anopheles parous count [EUPATH_0000196]': 'parous',
            'Anopheles nulliparous count [EUPATH_0000195]': 'nulliparous',
            'Gravid Anopheles gambiae count [EUPATH_0000198]': 'gravid_gambiae',
            'Gravid Anopheles funestus count [EUPATH_0000197]': 'gravid_funestus',
            'Gravid or semigravid other Anopheles species count [EUPATH_0020086]': 'gravid_other',
        })
        trap_df['date'] = pd.to_datetime(trap_df['date'])
        trap_df['gravid'] = (trap_df['gravid_gambiae'].fillna(0) +
                             trap_df['gravid_funestus'].fillna(0) +
                             trap_df['gravid_other'].fillna(0))
        # Filter to working traps with non-null counts
        trap_df = trap_df[(trap_df['working'] == 'Working') & trap_df['female_anopheles'].notna()]
        # Aggregate to household-date: mean/sum across rooms/traps
        trap_summary = trap_df.groupby(['Household_Id', 'date']).agg(
            mean_anopheles=('female_anopheles', 'mean'),
            n_traps=('female_anopheles', 'count'),
            total_dissected=('dissected_parity', 'sum'),
            total_parous=('parous', 'sum'),
            total_nulliparous=('nulliparous', 'sum'),
            total_gravid=('gravid', 'sum'),
        ).reset_index()
        trap_summary['parous_frac'] = np.where(
            trap_summary['total_dissected'] > 0,
            trap_summary['total_parous'] / trap_summary['total_dissected'],
            np.nan
        )

        # Load sporozoite data from participant repeated measures
        print("Loading PRISM2 sporozoite data...")
        part_ento = pd.read_csv(
            'data/PRISM2_cohort_Participant_repeated_measures.txt',
            sep='\t', low_memory=False,
            usecols=['Household_Id', 'Observation date [EUPATH_0004991]',
                     'Observation type [BFO_0000015]',
                     'Mosquitoes with sporozoites count [EUPATH_0020261]',
                     'Sleeping room number [EUPATH_0020170]'])
        part_ento = part_ento[part_ento['Observation type [BFO_0000015]'] == 'Entomology']
        part_ento = part_ento.rename(columns={
            'Observation date [EUPATH_0004991]': 'date',
            'Mosquitoes with sporozoites count [EUPATH_0020261]': 'sporozoite_pos',
            'Sleeping room number [EUPATH_0020170]': 'room',
        })
        part_ento['date'] = pd.to_datetime(part_ento['date'])
        # Deduplicate to room level, then sum across rooms to household-date
        sporo_room = part_ento.groupby(['Household_Id', 'date', 'room']).agg(
            sporozoite_pos=('sporozoite_pos', 'max')).reset_index()
        sporo_hh = sporo_room.groupby(['Household_Id', 'date']).agg(
            sporozoite_pos=('sporozoite_pos', 'sum')).reset_index()
        trap_summary = trap_summary.merge(
            sporo_hh[['Household_Id', 'date', 'sporozoite_pos']],
            on=['Household_Id', 'date'], how='left')
        trap_summary['sporozoite_pos'] = trap_summary['sporozoite_pos'].fillna(0)

        print(f"  {len(trap_summary)} household-nights of trap data across "
              f"{trap_summary['Household_Id'].nunique()} households")
        print(f"  {int(trap_summary['sporozoite_pos'].sum())} sporozoite-positive events")

        # Pre-compute haplotype data
        hap_color_map = generate_haplotype_color_map()
        df['haplotype_list'] = df['haplotype_id'].apply(
            lambda x: json.loads(x) if pd.notna(x) and x.startswith('[') else [])

        # Build per-individual haplotype registry (all haplotypes ever observed)
        individual_all_haplotypes = {}
        for pid, grp in df[df['haplotype_list'].apply(len) > 0].groupby('id'):
            all_haps = set()
            for haps in grp['haplotype_list']:
                all_haps.update(haps)
            individual_all_haplotypes[pid] = sorted(all_haps)

        # Compute max haplotype traces per household for padding
        max_hap_traces_per_hh = 0
        for hh_id in df['Household_Id'].unique():
            hh_data = df[(df['Household_Id'] == hh_id) & (df['haplotype_list'].apply(len) > 0)]
            hh_haps = set()
            for haps in hh_data['haplotype_list']:
                hh_haps.update(haps)
            max_hap_traces_per_hh = max(max_hap_traces_per_hh, len(hh_haps))
        print(f"  Max haplotype traces per household: {max_hap_traces_per_hh}")
    else:
        print(f"Loading PRISM data for {site.upper()} site...")
        df = pd.read_csv(f'data/prism_cleaned_{site}.csv', parse_dates=['date'])
        # Use LAMP for molecular detection
        df['molecular_positive'] = df['LAMP'] == 'Positive'
        df['molecular_tested'] = df['LAMP'].isin(['Positive', 'Negative'])
        molecular_label = 'LAMP'

        # Load PRISM1 household entomology (light trap) data
        print(f"Loading PRISM1 light trap data for {site.upper()}...")
        trap_df = pd.read_csv('data/PRISM_cohort_Household_repeated_measures.txt',
                              sep='\t', low_memory=False)
        trap_df = trap_df.rename(columns={
            'Collection date [EUPATH_0020003]': 'date',
            'Female Anopheles count [EUPATH_0000135]': 'female_anopheles',
            'Anopheles dissected for parity count [EUPATH_0000194]': 'dissected_parity',
            'Anopheles parous count [EUPATH_0000196]': 'parous',
            'Anopheles nulliparous count [EUPATH_0000195]': 'nulliparous',
            'Gravid Anopheles gambiae count [EUPATH_0000198]': 'gravid_gambiae',
            'Gravid Anopheles funestus count [EUPATH_0000197]': 'gravid_funestus',
            'Sporozoite-pos Anopheles count [EUPATH_0000218]': 'sporozoite_pos',
        })
        trap_df['date'] = pd.to_datetime(trap_df['date'])
        trap_df['gravid'] = (trap_df['gravid_gambiae'].fillna(0) +
                             trap_df['gravid_funestus'].fillna(0))
        # Filter to non-null female Anopheles counts (no "working" column in PRISM1)
        trap_df = trap_df[trap_df['female_anopheles'].notna()]
        # Filter to households present in this site's clinical data
        site_households = df['Household_Id'].unique()
        trap_df = trap_df[trap_df['Household_Id'].isin(site_households)]
        # Aggregate to household-date level
        trap_summary = trap_df.groupby(['Household_Id', 'date']).agg(
            mean_anopheles=('female_anopheles', 'mean'),
            n_traps=('female_anopheles', 'count'),
            total_dissected=('dissected_parity', 'sum'),
            total_parous=('parous', 'sum'),
            total_nulliparous=('nulliparous', 'sum'),
            total_gravid=('gravid', 'sum'),
            sporozoite_pos=('sporozoite_pos', 'sum'),
        ).reset_index()
        trap_summary['parous_frac'] = np.where(
            trap_summary['total_dissected'] > 0,
            trap_summary['total_parous'] / trap_summary['total_dissected'],
            np.nan
        )
        print(f"  {len(trap_summary)} household-nights of trap data across "
              f"{trap_summary['Household_Id'].nunique()} households")
        print(f"  {int(trap_summary['sporozoite_pos'].sum())} sporozoite-positive events")

    print(f"Loaded {len(df)} observations for {df['id'].nunique()} participants")

    # Get global date range for locked x-axis with 4-month padding
    global_date_min = df['date'].min() - pd.DateOffset(months=4)
    global_date_max = df['date'].max() + pd.DateOffset(months=4)

    # Get household statistics
    household_stats = df.groupby('Household_Id').agg({
        'id': 'nunique',
        'parasitedensity': lambda x: (x > 0).sum()
    }).rename(columns={
        'id': 'n_members',
        'parasitedensity': 'total_infections'
    })

    # Filter to multi-person households with infections
    multi_person = household_stats[
        (household_stats['n_members'] >= 2) &
        (household_stats['total_infections'] > 0)
    ].sort_values('total_infections', ascending=False)

    household_ids = multi_person.index.tolist()
    print(f"\nFound {len(household_ids)} multi-person households with infections")

    # Create figure with all households as separate traces
    fig = go.Figure()

    # Color definitions
    molecular_color = 'rgba(255, 237, 160, 0.6)'  # Used for LAMP/qPCR positive submicroscopic

    # Process each household and create trace groups
    all_traces = []
    household_trace_ranges = []  # Store (start, end, y_labels, y_positions, n_members, n_infections) for each household

    for hh_idx, household_id in enumerate(household_ids):
        household_data = df[df['Household_Id'] == household_id].copy()

        # Sort by age and create index
        household_data = household_data.sort_values(by='age_at_enrollment')
        unique_ids = household_data.drop_duplicates(subset=['id'], keep='first').copy()
        unique_ids['idx'] = range(len(unique_ids))
        household_data = household_data.merge(unique_ids[['id', 'idx']], on='id', how='left')

        # Store trace start index for this household
        trace_start = len(all_traces)

        # 1. All visits (background)
        all_traces.append(go.Scatter(
            x=household_data['date'],
            y=household_data['idx'],
            mode='markers',
            marker=dict(size=3, color='darkgray'),
            name='All visits',
            hoverinfo='skip',
            legendgroup='visits',
            showlegend=(hh_idx == 0)
        ))

        # 2. Fever visits
        fever = household_data[household_data['fever'] == 'Yes']
        all_traces.append(go.Scatter(
            x=fever['date'],
            y=fever['idx'],
            mode='markers',
            marker=dict(size=5, color='firebrick'),
            name='Fever',
            hoverinfo='skip',
            legendgroup='fever',
            showlegend=(hh_idx == 0)
        ))

        # 3. Molecular (LAMP/qPCR) negative
        mol_tested = household_data[household_data['molecular_tested'] == True].copy()
        mol_neg = mol_tested[mol_tested['molecular_positive'] == False]
        all_traces.append(go.Scatter(
            x=mol_neg['date'],
            y=mol_neg['idx'],
            mode='markers',
            marker=dict(size=8, color='rgba(0,0,0,0)', line=dict(color='darkgray', width=1)),
            name=f'{molecular_label} negative',
            hovertemplate=f'<b>{molecular_label} Negative</b><br>Date: %{{x|%Y-%m-%d}}<br>ID: %{{customdata[0]}}<extra></extra>',
            customdata=mol_neg[['id']].values if len(mol_neg) > 0 else [],
            legendgroup='mol_neg',
            showlegend=(hh_idx == 0)
        ))

        # 4. Molecular (LAMP/qPCR) positive - SUBMICROSCOPIC ONLY (molecular+, microscopy-)
        mol_pos_submicro = mol_tested[(mol_tested['molecular_positive'] == True) &
                                       (mol_tested['parasitedensity'] == 0)].copy()

        if len(mol_pos_submicro) > 0 and is_prism2:
            # For PRISM2: density-dependent sizing and rich tooltips
            # Size based on qPCR density (log scale, min size 8, max ~18)
            qpcr_dens = mol_pos_submicro['qpcr_density'].fillna(0).replace(0, 0.01)
            marker_size = 8 + 2 * np.log10(qpcr_dens + 1)
            marker_size = marker_size.clip(lower=8, upper=18)

            # Build hover text with densities
            hover_text = []
            for _, row in mol_pos_submicro.iterrows():
                def fmt_density(val):
                    if pd.isna(val) or val == 0:
                        return None
                    if val >= 1e6:
                        return f'{val/1e6:.1f}M'
                    elif val >= 1e3:
                        return f'{val/1e3:.1f}K'
                    elif val >= 1:
                        return f'{val:.1f}'
                    else:
                        return f'{val:.4f}'

                lines = [f'<b>qPCR Positive (Submicroscopic)</b>',
                         f'Date: {row["date"].strftime("%Y-%m-%d")}',
                         f'ID: {int(row["id"])}']

                qpcr_d = fmt_density(row.get('qpcr_density'))
                if qpcr_d:
                    lines.append(f'qPCR density: {qpcr_d} /µL')

                gam_d = fmt_density(row.get('gametocytes_qpcr_density'))
                if gam_d:
                    lines.append(f'Gametocytes: {gam_d} /µL')

                fem_d = fmt_density(row.get('gametocytes_female_density'))
                if fem_d:
                    lines.append(f'  Female: {fem_d} /µL')

                male_d = fmt_density(row.get('gametocytes_male_density'))
                if male_d:
                    lines.append(f'  Male: {male_d} /µL')

                # COI and haplotype
                coi = row.get('coi')
                if pd.notna(coi) and coi > 0:
                    lines.append(f'COI: {int(coi)}')
                hap = row.get('haplotype_id')
                if pd.notna(hap) and 'pfama' in str(hap):
                    hap_ids = [h.replace('pfama1.', '') for h in str(hap).replace('[', '').replace(']', '').replace('"', '').replace("'", "").split(',')]
                    lines.append(f'pfama1: [{", ".join(hap_ids)}]')

                # Membrane feeding results
                mosq_dissected = row.get('mosquitoes_dissected')
                mosq_oocyst = row.get('mosquitoes_oocyst_positive')
                if pd.notna(mosq_dissected) and mosq_dissected > 0:
                    lines.append(f'Feeding: {int(mosq_oocyst)}/{int(mosq_dissected)} oocyst+')

                hover_text.append('<br>'.join(lines))

            all_traces.append(go.Scatter(
                x=mol_pos_submicro['date'],
                y=mol_pos_submicro['idx'],
                mode='markers',
                marker=dict(size=marker_size, color=molecular_color, line=dict(color='darkgray', width=1)),
                name=f'{molecular_label} positive (submicroscopic)',
                hovertemplate='%{hovertext}<extra></extra>',
                hovertext=hover_text,
                legendgroup='mol_pos',
                showlegend=(hh_idx == 0)
            ))
        else:
            # For PRISM (LAMP) or empty: fixed size, simple tooltip
            all_traces.append(go.Scatter(
                x=mol_pos_submicro['date'],
                y=mol_pos_submicro['idx'],
                mode='markers',
                marker=dict(size=10, color=molecular_color, line=dict(color='darkgray', width=1)),
                name=f'{molecular_label} positive (submicroscopic)',
                hovertemplate=f'<b>{molecular_label} Positive</b><br>Date: %{{x|%Y-%m-%d}}<br>ID: %{{customdata[0]}}<extra></extra>',
                customdata=mol_pos_submicro[['id']].values if len(mol_pos_submicro) > 0 else [],
                legendgroup='mol_pos',
                showlegend=(hh_idx == 0)
            ))

        # 5. Microscopy negative (only for samples not tested by LAMP/qPCR - those are shown in trace 3)
        micro_only_untested = household_data[(household_data['molecular_tested'] == False) &
                                              (household_data['parasitedensity'].notna())].copy()
        micro_neg = micro_only_untested[micro_only_untested['parasitedensity'] == 0]
        all_traces.append(go.Scatter(
            x=micro_neg['date'],
            y=micro_neg['idx'],
            mode='markers',
            marker=dict(size=10, color='rgba(0,0,0,0)', line=dict(color='darkgray', width=1)),
            name='Microscopy negative',
            hovertemplate='<b>Microscopy Negative</b><br>Date: %{x|%Y-%m-%d}<br>ID: %{customdata[0]}<extra></extra>',
            customdata=micro_neg[['id']].values if len(micro_neg) > 0 else [],
            legendgroup='micro_neg',
            showlegend=(hh_idx == 0)
        ))

        # 6. Parasite positive (ALL microscopy positives, regardless of molecular testing)
        parasite_pos = household_data[household_data['parasitedensity'] > 0].copy()
        if len(parasite_pos) > 0:
            marker_size = 50 * np.log10(parasite_pos['parasitedensity'])
            marker_size[marker_size < 10] = 10
            marker_size = marker_size / 4.5

            # Helper for formatting density values
            def fmt_dens(val):
                if pd.isna(val) or val == 0:
                    return None
                if val >= 1e6:
                    return f'{val/1e6:.1f}M'
                elif val >= 1e3:
                    return f'{val/1e3:.1f}K'
                elif val >= 1:
                    return f'{val:.1f}'
                else:
                    return f'{val:.4f}'

            hover_text = []
            for _, row in parasite_pos.iterrows():
                density = row['parasitedensity']
                if density >= 1e6:
                    txt = f'{density/1e6:.1f}M'
                elif density >= 1e3:
                    txt = f'{density/1e3:.1f}K'
                else:
                    txt = f'{int(density)}'

                # Add fever, gametocyte, and treatment status to hover text
                extra_info = []
                if row['fever'] == 'Yes':
                    extra_info.append('Fever: Yes')

                # Gametocytes - show density for PRISM2, just Yes/No for PRISM
                if is_prism2:
                    gam_micro_d = fmt_dens(row.get('gametocyte_density'))
                    if gam_micro_d:
                        extra_info.append(f'Gametocytes (microscopy): {gam_micro_d} /µL')
                    elif row.get('gametocytes') == 'Yes':
                        extra_info.append('Gametocytes (microscopy): Yes')
                else:
                    if row.get('gametocytes') == 'Yes':
                        extra_info.append('Gametocytes: Yes')

                # For PRISM2: add qPCR densities
                if is_prism2:
                    qpcr_d = fmt_dens(row.get('qpcr_density'))
                    if qpcr_d:
                        extra_info.append(f'qPCR density: {qpcr_d} /µL')
                    gam_d = fmt_dens(row.get('gametocytes_qpcr_density'))
                    if gam_d:
                        extra_info.append(f'Gametocytes (qPCR): {gam_d} /µL')
                    fem_d = fmt_dens(row.get('gametocytes_female_density'))
                    if fem_d:
                        extra_info.append(f'  Female: {fem_d} /µL')
                    male_d = fmt_dens(row.get('gametocytes_male_density'))
                    if male_d:
                        extra_info.append(f'  Male: {male_d} /µL')
                    # COI and haplotype
                    coi = row.get('coi')
                    if pd.notna(coi) and coi > 0:
                        extra_info.append(f'COI: {int(coi)}')
                    hap = row.get('haplotype_id')
                    if pd.notna(hap) and 'pfama' in str(hap):
                        hap_ids = [h.replace('pfama1.', '') for h in str(hap).replace('[', '').replace(']', '').replace('"', '').replace("'", "").split(',')]
                        extra_info.append(f'pfama1: [{", ".join(hap_ids)}]')
                    # Membrane feeding results
                    mosq_dissected = row.get('mosquitoes_dissected')
                    mosq_oocyst = row.get('mosquitoes_oocyst_positive')
                    if pd.notna(mosq_dissected) and mosq_dissected > 0:
                        extra_info.append(f'Feeding: {int(mosq_oocyst)}/{int(mosq_dissected)} oocyst+')

                if pd.notna(row.get('antimalarial')) and row.get('antimalarial') != 'No malaria medications given' and row.get('antimalarial') != '' and row.get('antimalarial') != 'Not applicable - no malaria diagnosed today':
                    # Shorten the treatment text for display
                    treatment = row['antimalarial']
                    if 'Artmether-lumefantrine' in treatment or 'Artemether-lumefantrine' in treatment:
                        treatment = 'AL treatment'
                    elif 'Quinine' in treatment and 'complicated' in treatment:
                        treatment = 'Quinine (complicated)'
                    elif 'Quinine' in treatment and '14 days' in treatment:
                        treatment = 'Quinine (repeat)'
                    elif 'Quinine' in treatment and 'pregnancy' in treatment:
                        treatment = 'Quinine (pregnancy)'
                    elif 'Artesunate' in treatment:
                        treatment = 'Artesunate (complicated)'
                    extra_info.append(f'Treatment: {treatment}')

                hover_line = f"<b>Parasite Positive</b><br>Microscopy: {txt} /µL<br>Date: {row['date'].strftime('%Y-%m-%d')}<br>ID: {int(row['id'])}"
                if extra_info:
                    hover_line += '<br>' + '<br>'.join(extra_info)
                hover_text.append(hover_line)

            all_traces.append(go.Scatter(
                x=parasite_pos['date'],
                y=parasite_pos['idx'],
                mode='markers',
                marker=dict(
                    size=marker_size,
                    color=np.log10(parasite_pos['parasitedensity']),
                    colorscale='YlOrRd',
                    cmin=1,
                    cmax=5.5,
                    line=dict(color='darkgray', width=0.5),
                    colorbar=dict(
                        title='Parasite<br>Density<br>(log10)',
                        tickvals=[1, 2, 3, 4, 5],
                        ticktext=['10', '100', '1K', '10K', '100K'],
                        len=0.4,
                        y=0.4,
                        yanchor='top'
                    ) if hh_idx == 0 else None
                ),
                name='Parasite positive',
                hovertemplate='%{hovertext}<extra></extra>',
                hovertext=hover_text,
                legendgroup='parasite',
                showlegend=(hh_idx == 0)
            ))

            # 7. Gametocytes (with variable border width for PRISM2 based on oocyst prevalence)
            parasite_pos_gam = parasite_pos[parasite_pos['gametocytes'] == 'Yes'].copy()
            if len(parasite_pos_gam) > 0:
                marker_size_gam = 50 * np.log10(parasite_pos_gam['parasitedensity'])
                marker_size_gam[marker_size_gam < 10] = 10
                marker_size_gam = marker_size_gam / 4.5

                if is_prism2:
                    # Variable border width based on oocyst prevalence
                    # >50% = width 3, >5% = width 2, >0% = width 1, no feeding/0% = width 2 (default)
                    oocyst_prev = parasite_pos_gam['oocyst_prevalence'].fillna(-1)

                    # Split into categories
                    high_inf = parasite_pos_gam[oocyst_prev > 0.5]
                    med_inf = parasite_pos_gam[(oocyst_prev > 0.05) & (oocyst_prev <= 0.5)]
                    low_inf = parasite_pos_gam[(oocyst_prev > 0) & (oocyst_prev <= 0.05)]
                    no_inf = parasite_pos_gam[oocyst_prev <= 0]  # includes no feeding data

                    # Add traces for each category
                    for subset, width, show_legend in [
                        (high_inf, 4, False),   # >50% infectious
                        (med_inf, 3, False),    # >5% infectious
                        (low_inf, 2, False),    # >0% infectious
                        (no_inf, 1.5, (hh_idx == 0))  # no feeding or 0%
                    ]:
                        if len(subset) > 0:
                            sz = 50 * np.log10(subset['parasitedensity'])
                            sz[sz < 10] = 10
                            sz = sz / 4.5
                            all_traces.append(go.Scatter(
                                x=subset['date'],
                                y=subset['idx'],
                                mode='markers',
                                marker=dict(size=sz + 2, color='rgba(0,0,0,0)',
                                           line=dict(color='olive', width=width)),
                                name='Gametocytes detected',
                                hoverinfo='skip',
                                legendgroup='gametocytes',
                                showlegend=show_legend
                            ))
                        else:
                            all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
                else:
                    # PRISM: single trace with fixed width
                    all_traces.append(go.Scatter(
                        x=parasite_pos_gam['date'],
                        y=parasite_pos_gam['idx'],
                        mode='markers',
                        marker=dict(size=marker_size_gam + 2, color='rgba(0,0,0,0)', line=dict(color='olive', width=2)),
                        name='Gametocytes detected',
                        hoverinfo='skip',
                        legendgroup='gametocytes',
                        showlegend=(hh_idx == 0)
                    ))
            else:
                if is_prism2:
                    # Add 4 empty traces for PRISM2 to maintain indexing
                    for _ in range(4):
                        all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
                else:
                    all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
        else:
            # Add empty traces to maintain consistent indexing
            all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
            all_traces.append(go.Scatter(x=[], y=[], showlegend=False))

        # 8. Mosquito trap counts
        if trap_summary is not None:
            hh_traps = trap_summary[trap_summary['Household_Id'] == household_id].copy()
            if len(hh_traps) > 0:
                mosquito_y = -1
                marker_size_mosq = np.maximum(3, 3.75 * np.sqrt(hh_traps['mean_anopheles']))

                # Color gradient: forest green (0% parous) → olive (100% parous)
                # Forest green: rgb(34, 139, 34), Olive: rgb(128, 128, 0)
                colors_mosq = []
                hover_text_mosq = []
                for _, row in hh_traps.iterrows():
                    # Color based on parous fraction
                    frac = row['parous_frac']
                    if pd.isna(frac):
                        colors_mosq.append('rgba(34, 139, 34, 0.5)')
                    else:
                        frac_clamped = max(0.0, min(1.0, frac))
                        r = int(34 + 94 * frac_clamped)
                        g = int(139 - 11 * frac_clamped)
                        b = int(34 - 34 * frac_clamped)
                        colors_mosq.append(f'rgba({r}, {g}, {b}, 0.5)')

                    # Tooltip
                    avg = row['mean_anopheles']
                    lines = [f'<b>CDC Light Trap</b>',
                             f'Date: {row["date"].strftime("%Y-%m-%d")}',
                             f'Avg female Anopheles/trap: {avg:.1f}',
                             f'Traps: {int(row["n_traps"])}']

                    dissected = row.get('total_dissected', 0)
                    if dissected > 0:
                        parous = int(row['total_parous'])
                        nullip = int(row['total_nulliparous'])
                        lines.append(f'Parity: {parous}/{int(dissected)} parous ({frac:.0%})')
                        lines.append(f'Nulliparous: {nullip}')
                    gravid = int(row.get('total_gravid', 0))
                    if gravid > 0:
                        lines.append(f'Gravid: {gravid}')

                    sporo = row.get('sporozoite_pos', 0)
                    if sporo > 0:
                        lines.append(f'SPOROZOITE POSITIVE: {int(sporo)}')

                    hover_text_mosq.append('<br>'.join(lines))

                all_traces.append(go.Scatter(
                    x=hh_traps['date'],
                    y=[mosquito_y] * len(hh_traps),
                    mode='markers',
                    marker=dict(
                        size=marker_size_mosq,
                        color=colors_mosq,
                    ),
                    name='Mosquito traps',
                    hovertemplate='%{hovertext}<extra></extra>',
                    hovertext=hover_text_mosq,
                    legendgroup='mosquitoes',
                    showlegend=(hh_idx == 0)
                ))

                # 9. Sporozoite-positive red dots
                sporo_nights = hh_traps[hh_traps['sporozoite_pos'] > 0]
                if len(sporo_nights) > 0:
                    all_traces.append(go.Scatter(
                        x=sporo_nights['date'],
                        y=[mosquito_y] * len(sporo_nights),
                        mode='markers',
                        marker=dict(size=5, color='red'),
                        name='Sporozoite positive',
                        hoverinfo='skip',
                        legendgroup='sporozoite',
                        showlegend=(hh_idx == 0)
                    ))
                else:
                    all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
            else:
                all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
                all_traces.append(go.Scatter(x=[], y=[], showlegend=False))

        # 10. Haplotype indicators (PRISM2 only)
        hap_trace_start = len(all_traces)
        if is_prism2:
            hh_hap_data = household_data[household_data['haplotype_list'].apply(len) > 0]
            hh_unique_haps = sorted(set(h for haps in hh_hap_data['haplotype_list'] for h in haps))
            n_hap_traces = 0

            # Grid layout: max 5 rows per column, balanced distribution
            max_per_col = 5
            col_offset_days = pd.Timedelta(days=5)
            y_base = 0.25  # shifted up from 0.15
            band_height = 0.30
            row_height = band_height / max_per_col

            # Pre-compute balanced grid mapping per individual
            def balanced_grid(slot_k, n_total):
                """Map slot index to (row, col) with balanced column fill."""
                n_cols = (n_total - 1) // max_per_col + 1
                rows_per_col = n_total // n_cols
                extra = n_total % n_cols
                # First 'extra' columns get rows_per_col+1, rest get rows_per_col
                col = 0
                remaining = slot_k
                for c in range(n_cols):
                    col_size = rows_per_col + (1 if c < extra else 0)
                    if remaining < col_size:
                        return remaining, c, n_cols
                    remaining -= col_size
                    col = c + 1
                return remaining, col, n_cols

            for haplotype in hh_unique_haps:
                # Rows where this haplotype is present
                mask = hh_hap_data['haplotype_list'].apply(lambda hl: haplotype in hl)
                subset = hh_hap_data[mask]
                if len(subset) == 0:
                    all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
                    n_hap_traces += 1
                    continue

                # Compute x/y positions using per-individual fixed slot with balanced grid
                x_vals = []
                y_vals = []
                for _, row in subset.iterrows():
                    pid = row['id']
                    idx = row['idx']
                    ind_haps = individual_all_haplotypes.get(pid, [haplotype])
                    slot_k = ind_haps.index(haplotype)
                    grid_row, grid_col, n_cols = balanced_grid(slot_k, len(ind_haps))
                    y_val = idx + y_base + (grid_row + 0.5) * row_height
                    x_val = row['date'] + (grid_col - (n_cols - 1) / 2) * col_offset_days
                    y_vals.append(y_val)
                    x_vals.append(x_val)

                hover_text = [
                    f'<b>{haplotype}</b><br>Date: {row["date"].strftime("%Y-%m-%d")}<br>ID: {int(row["id"])}'
                    for _, row in subset.iterrows()
                ]

                all_traces.append(go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode='markers',
                    marker=dict(
                        symbol='asterisk',
                        size=6,
                        color='rgba(0,0,0,0)',
                        line=dict(width=1, color=hap_color_map.get(haplotype, 'gray'))
                    ),
                    showlegend=False,
                    hovertemplate='%{hovertext}<extra></extra>',
                    hovertext=hover_text,
                ))
                n_hap_traces += 1

            # Pad to max_hap_traces_per_hh for consistent trace indexing
            for _ in range(max_hap_traces_per_hh - n_hap_traces):
                all_traces.append(go.Scatter(x=[], y=[], showlegend=False))

        trace_end = len(all_traces)

        # Create y-axis labels for this household
        y_labels = []
        y_positions = []
        subsample = max(1, len(unique_ids) // 50)
        for _, row in unique_ids.iloc[::subsample].iterrows():
            age = int(row['age_at_enrollment']) if pd.notna(row['age_at_enrollment']) else '?'
            gender = row['gender'][0] if pd.notna(row['gender']) else '?'
            y_labels.append(f"{age} {gender}")
            y_positions.append(row['idx'])

        # Add gridline-only ticks for ALL row positions (not just labeled ones)
        all_y_positions = list(range(len(unique_ids)))
        all_y_labels = ['' if i not in y_positions else y_labels[y_positions.index(i)]
                        for i in all_y_positions]

        if trap_summary is not None:
            y_positions_with_bottom = [-1] + all_y_positions
            y_labels_with_bottom = ['Traps'] + all_y_labels
        else:
            y_positions_with_bottom = all_y_positions
            y_labels_with_bottom = all_y_labels

        # Get household stats
        n_members = multi_person.loc[household_id, 'n_members']
        n_infections = multi_person.loc[household_id, 'total_infections']

        # Store info for button creation later
        household_trace_ranges.append({
            'household_id': household_id,
            'trace_start': trace_start,
            'trace_end': trace_end,
            'hap_trace_start': hap_trace_start,
            'y_labels': y_labels_with_bottom,
            'y_positions': y_positions_with_bottom,
            'n_members': n_members,
            'n_infections': n_infections,
            'n_unique_ids': len(unique_ids)
        })

    # Add all traces to figure
    for trace in all_traces:
        fig.add_trace(trace)

    # Now create buttons with correct total trace count
    total_traces = len(all_traces)
    all_buttons = []

    for hh_info in household_trace_ranges:
        # Build visibility array: show only traces for this household
        visible = [False] * total_traces
        for i in range(hh_info['trace_start'], hh_info['trace_end']):
            visible[i] = True

        button = dict(
            label=f"HH {hh_info['household_id']} ({int(hh_info['n_members'])}m, {int(hh_info['n_infections'])}i)",
            method="update",
            args=[
                {"visible": visible},
                {
                    "title": f"Household {hh_info['household_id']} - {int(hh_info['n_members'])} members, {int(hh_info['n_infections'])} microscopy-positive observations",
                    "yaxis.tickvals": hh_info['y_positions'],
                    "yaxis.ticktext": hh_info['y_labels'],
                    "yaxis.range": [-1.8 if trap_summary is not None else -0.5, hh_info['n_unique_ids'] - 0.5],
                    "xaxis.range": [global_date_min, global_date_max]
                }
            ]
        )
        all_buttons.append(button)

    # Set initial visibility using the first button's visibility array
    if len(all_buttons) > 0:
        initial_visibility = all_buttons[0]['args'][0]['visible']
        for i, trace in enumerate(fig.data):
            trace.visible = initial_visibility[i]

    # Get first household info for initial display
    household_id = household_ids[0]
    household_data = df[df['Household_Id'] == household_id].copy()
    household_data = household_data.sort_values(by='age_at_enrollment')
    unique_ids = household_data.drop_duplicates(subset=['id'], keep='first').copy()
    unique_ids['idx'] = range(len(unique_ids))

    y_labels = []
    y_positions = []
    subsample = max(1, len(unique_ids) // 50)
    for _, row in unique_ids.iloc[::subsample].iterrows():
        age = int(row['age_at_enrollment']) if pd.notna(row['age_at_enrollment']) else '?'
        gender = row['gender'][0] if pd.notna(row['gender']) else '?'
        y_labels.append(f"{age} {gender}")
        y_positions.append(row['idx'])

    # Add ticks for ALL row positions to ensure gridlines at every row
    all_y_positions = list(range(len(unique_ids)))
    all_y_labels = ['' if i not in y_positions else y_labels[y_positions.index(i)]
                    for i in all_y_positions]

    if trap_summary is not None:
        y_positions = [-1] + all_y_positions
        y_labels = ['Traps'] + all_y_labels
    else:
        y_positions = all_y_positions
        y_labels = all_y_labels

    # Update layout with dropdown
    fig.update_layout(
        updatemenus=[
            dict(
                buttons=all_buttons,
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                active=0,
                x=0.01,
                xanchor="left",
                y=1.15,
                yanchor="top",
                bgcolor="lightblue",
                bordercolor="black",
                borderwidth=1
            )
        ],
        title=dict(
            text=f"{'PRISM2' if is_prism2 else 'PRISM'} Household Viewer - {site.upper()} ({len(household_ids)} households)",
            font=dict(size=18),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title='Date',
            gridcolor='lightgray',
            gridwidth=0.5,
            range=[global_date_min, global_date_max]
        ),
        yaxis=dict(
            title='Age (years) & Gender',
            tickmode='array',
            tickvals=y_positions,
            ticktext=y_labels,
            gridcolor='lightgray',
            gridwidth=0.5,
            range=[-1.8 if trap_summary is not None else -0.5, len(unique_ids) - 0.5],
            showgrid=True,
            griddash='solid',
            zeroline=True,
            zerolinecolor='lightgray',
            zerolinewidth=0.5
        ),
        plot_bgcolor='white',
        hovermode='closest',
        height=800,
        showlegend=True,
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.98,
            xanchor='left',
            x=1.02,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='black',
            borderwidth=1
        )
    )

    # Save to HTML
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a mapping from household_id to index for synchronization
    household_id_to_index = {str(hh_info['household_id']): idx
                             for idx, hh_info in enumerate(household_trace_ranges)}

    # Build haplotype trace range info for JS
    hap_trace_ranges_js = json.dumps([
        {'start': hh['hap_trace_start'], 'end': hh['trace_end']}
        for hh in household_trace_ranges
    ])

    # Add custom JavaScript for keyboard navigation and buttons
    keyboard_nav_script = """
    <script>
    // Track current household index
    var currentHouseholdIndex = 0;
    var totalHouseholds = """ + str(len(all_buttons)) + """;
    var householdIdToIndex = """ + str(household_id_to_index) + """;
    var hapTraceRanges = """ + hap_trace_ranges_js + """;
    var updatingFromCode = false;  // Flag to prevent circular updates

    // Keyboard navigation
    document.addEventListener('keydown', function(event) {
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
            nextHousehold();
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
            previousHousehold();
        }
    });

    function nextHousehold() {
        if (currentHouseholdIndex < totalHouseholds - 1) {
            selectHousehold(currentHouseholdIndex + 1);
        }
    }

    function previousHousehold() {
        if (currentHouseholdIndex > 0) {
            selectHousehold(currentHouseholdIndex - 1);
        }
    }

    function selectHousehold(index) {
        if (index < 0 || index >= totalHouseholds) return;

        currentHouseholdIndex = index;
        updatingFromCode = true;  // Set flag before updating

        var graphDiv = document.querySelector('.plotly-graph-div');
        if (graphDiv && graphDiv.layout && graphDiv.layout.updatemenus) {
            var button = graphDiv.layout.updatemenus[0].buttons[index];
            if (button && button.args) {
                // Apply haplotype checkbox state to visibility
                var vis = button.args[0].visible.slice();
                var showHap = document.getElementById('hapCheckbox');
                if (showHap && !showHap.checked) {
                    var range = hapTraceRanges[index];
                    for (var j = range.start; j < range.end; j++) {
                        vis[j] = false;
                    }
                }
                // Update both the plot and the dropdown's active state
                Plotly.relayout(graphDiv, {
                    'updatemenus[0].active': index
                }).then(function() {
                    return Plotly.relayout(graphDiv, button.args[1]);
                }).then(function() {
                    return Plotly.restyle(graphDiv, {visible: vis});
                }).then(function() {
                    updatingFromCode = false;  // Clear flag after update completes
                    updateNavigationButtons();
                });
            }
        }
    }

    function updateNavigationButtons() {
        var prevBtn = document.getElementById('prevBtn');
        var nextBtn = document.getElementById('nextBtn');
        if (prevBtn) prevBtn.disabled = (currentHouseholdIndex === 0);
        if (nextBtn) nextBtn.disabled = (currentHouseholdIndex === totalHouseholds - 1);

        var counterSpan = document.getElementById('hhCounter');
        if (counterSpan) {
            counterSpan.textContent = (currentHouseholdIndex + 1) + ' / ' + totalHouseholds;
        }
    }

    function toggleHaplotypes(checked) {
        var graphDiv = document.querySelector('.plotly-graph-div');
        if (!graphDiv) return;
        var range = hapTraceRanges[currentHouseholdIndex];
        var indices = [];
        var vis = [];
        for (var j = range.start; j < range.end; j++) {
            indices.push(j);
            vis.push(checked);
        }
        Plotly.restyle(graphDiv, {visible: vis}, indices);
    }

    // Extract household ID from title string
    function getHouseholdIdFromTitle(title) {
        if (!title) return null;
        var match = title.match(/Household (\\d+)/);
        return match ? match[1] : null;
    }

    // Track dropdown changes - using the polling approach that actually works
    // Performance: checking a property every 100ms is negligible overhead
    var lastKnownActive = 0;

    function pollDropdownState() {
        if (updatingFromCode) {
            return;
        }

        var graphDiv = document.querySelector('.plotly-graph-div');
        if (graphDiv && graphDiv.layout && graphDiv.layout.updatemenus && graphDiv.layout.updatemenus[0]) {
            var active = graphDiv.layout.updatemenus[0].active;
            if (typeof active === 'number' && active !== lastKnownActive) {
                lastKnownActive = active;
                if (active !== currentHouseholdIndex) {
                    currentHouseholdIndex = active;
                    updateNavigationButtons();
                }
            }
        }
    }

    function setupDropdownTracking() {
        // Start polling for dropdown state changes
        // 100ms polling has negligible performance impact - it's just reading a property
        setInterval(pollDropdownState, 100);
    }

    // Add navigation buttons to the page
    window.addEventListener('load', function() {
        var graphDiv = document.querySelector('.plotly-graph-div');
        if (graphDiv) {
            var navDiv = document.createElement('div');
            navDiv.style.cssText = 'position: absolute; top: 10px; right: 10px; z-index: 1000; background: white; padding: 10px; border: 1px solid #ccc; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';
            navDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <button id="prevBtn" onclick="previousHousehold()" style="padding: 5px 15px; cursor: pointer; font-size: 14px;">← Previous</button>
                    <span id="hhCounter" style="font-size: 14px; min-width: 60px; text-align: center;">1 / ${totalHouseholds}</span>
                    <button id="nextBtn" onclick="nextHousehold()" style="padding: 5px 15px; cursor: pointer; font-size: 14px;">Next →</button>
                </div>
                <div style="font-size: 11px; color: #666; margin-top: 5px; text-align: center;">Use ← → arrow keys</div>""" + ("""
                <div style="margin-top: 6px; text-align: center;">
                    <label style="font-size: 12px; cursor: pointer;"><input type="checkbox" id="hapCheckbox" checked onchange="toggleHaplotypes(this.checked)"> Show haplotypes</label>
                </div>""" if is_prism2 else "") + """
            `;
            graphDiv.parentNode.insertBefore(navDiv, graphDiv);
            updateNavigationButtons();

            // Setup dropdown tracking
            setupDropdownTracking();
        }
    });
    </script>
    """

    fig.write_html(
        output_path,
        include_plotlyjs='cdn',
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )

    # Append custom JavaScript by modifying the HTML file
    with open(output_path, 'r') as f:
        html_content = f.read()

    # Insert the keyboard navigation script before the closing body tag
    html_content = html_content.replace('</body>', keyboard_nav_script + '\n</body>')

    with open(output_path, 'w') as f:
        f.write(html_content)

    print(f"\nGenerated interactive viewer: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")

    return fig


if __name__ == '__main__':
    # Generate viewer for each PRISM site
    sites = ['nagongera', 'walukuba', 'kihihi']

    for site in sites:
        print("\n" + "=" * 80)
        print(f"GENERATING VIEWER FOR {site.upper()}")
        print("=" * 80)
        create_interactive_viewer(site=site, output_file=f'docs/{site}.html')

    # Generate viewer for PRISM2
    print("\n" + "=" * 80)
    print("GENERATING VIEWER FOR PRISM2 (NAGONGERA)")
    print("=" * 80)
    create_interactive_viewer(site='nagongera', output_file='docs/nagongera_prism2.html', is_prism2=True)

    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    print("\nCreated HTML files in docs/ directory:")
    print("  - docs/nagongera.html")
    print("  - docs/walukuba.html")
    print("  - docs/kihihi.html")
    print("  - docs/nagongera_prism2.html")
