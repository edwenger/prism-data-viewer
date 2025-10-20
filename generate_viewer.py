"""
Generate interactive household viewer HTML file

This script creates a standalone HTML file with an interactive household viewer
that can be hosted on GitHub Pages.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path


def create_interactive_viewer(site='nagongera', output_file='docs/index.html'):
    """
    Create an interactive household viewer with dropdown navigation.

    Parameters
    ----------
    site : str
        Site name ('nagongera', 'walukuba', or 'kihihi')
    output_file : str or Path
        Output HTML file path
    """

    print(f"Loading PRISM data for {site.upper()} site...")
    df = pd.read_csv(f'data/prism_cleaned_{site}.csv', parse_dates=['date'])
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
    lamp_color = 'rgba(255, 237, 160, 0.6)'

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

        # 3. LAMP negative
        lamp = household_data[household_data['LAMP'].isin(['Positive', 'Negative'])].copy()
        lamp_neg = lamp[lamp['LAMP'] == 'Negative']
        all_traces.append(go.Scatter(
            x=lamp_neg['date'],
            y=lamp_neg['idx'],
            mode='markers',
            marker=dict(size=8, color='rgba(0,0,0,0)', line=dict(color='darkgray', width=1)),
            name='LAMP negative',
            hovertemplate='<b>LAMP Negative</b><br>Date: %{x|%Y-%m-%d}<br>ID: %{customdata[0]}<extra></extra>',
            customdata=lamp_neg[['id']].values if len(lamp_neg) > 0 else [],
            legendgroup='lamp_neg',
            showlegend=(hh_idx == 0)
        ))

        # 4. LAMP positive
        lamp_pos = lamp[lamp['LAMP'] == 'Positive']
        all_traces.append(go.Scatter(
            x=lamp_pos['date'],
            y=lamp_pos['idx'],
            mode='markers',
            marker=dict(size=10, color=lamp_color, line=dict(color='darkgray', width=1)),
            name='LAMP positive (submicroscopic)',
            hovertemplate='<b>LAMP Positive</b><br>Date: %{x|%Y-%m-%d}<br>ID: %{customdata[0]}<extra></extra>',
            customdata=lamp_pos[['id']].values if len(lamp_pos) > 0 else [],
            legendgroup='lamp_pos',
            showlegend=(hh_idx == 0)
        ))

        # 5. Microscopy negative
        micro_only = household_data[(~household_data['LAMP'].isin(['Positive', 'Negative', 'No result'])) &
                                    (household_data['parasitedensity'].notna())].copy()
        micro_neg = micro_only[micro_only['parasitedensity'] == 0]
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

        # 6. Parasite positive
        parasite_pos = micro_only[micro_only['parasitedensity'] > 0].copy()
        if len(parasite_pos) > 0:
            marker_size = 50 * np.log10(parasite_pos['parasitedensity'])
            marker_size[marker_size < 10] = 10
            marker_size = marker_size / 4.5

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
                if row['gametocytes'] == 'Yes':
                    extra_info.append('Gametocytes: Yes')
                if pd.notna(row['antimalarial']) and row['antimalarial'] != 'No malaria medications given' and row['antimalarial'] != '':
                    # Shorten the treatment text for display
                    treatment = row['antimalarial']
                    if 'Artmether-lumefantrine' in treatment:
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

                hover_line = f"<b>Parasite Positive</b><br>Density: {txt} /µL<br>Date: {row['date'].strftime('%Y-%m-%d')}<br>ID: {int(row['id'])}"
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

            # 7. Gametocytes
            parasite_pos_gam = parasite_pos[parasite_pos['gametocytes'] == 'Yes'].copy()
            if len(parasite_pos_gam) > 0:
                marker_size_gam = 50 * np.log10(parasite_pos_gam['parasitedensity'])
                marker_size_gam[marker_size_gam < 10] = 10
                marker_size_gam = marker_size_gam / 4.5

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
                all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
        else:
            # Add empty traces to maintain consistent indexing
            all_traces.append(go.Scatter(x=[], y=[], showlegend=False))
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
                    "yaxis.range": [-0.5, hh_info['n_unique_ids'] - 0.5],
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
            text=f"PRISM Household Viewer - {site.upper()} ({len(household_ids)} households)",
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
            range=[-0.5, len(unique_ids) - 0.5],
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

    # Add custom JavaScript for keyboard navigation and buttons
    keyboard_nav_script = """
    <script>
    // Track current household index
    var currentHouseholdIndex = 0;
    var totalHouseholds = """ + str(len(all_buttons)) + """;
    var householdIdToIndex = """ + str(household_id_to_index) + """;
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
                // Update both the plot and the dropdown's active state
                Plotly.relayout(graphDiv, {
                    'updatemenus[0].active': index
                }).then(function() {
                    return Plotly.relayout(graphDiv, button.args[1]);
                }).then(function() {
                    return Plotly.restyle(graphDiv, button.args[0]);
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
                <div style="font-size: 11px; color: #666; margin-top: 5px; text-align: center;">Use ← → arrow keys</div>
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
    # Generate viewer for each site
    sites = ['nagongera', 'walukuba', 'kihihi']

    for site in sites:
        print("\n" + "=" * 80)
        print(f"GENERATING VIEWER FOR {site.upper()}")
        print("=" * 80)
        create_interactive_viewer(site=site, output_file=f'docs/{site}.html')

    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    print("\nCreated HTML files in docs/ directory:")
    print("  - docs/nagongera.html")
    print("  - docs/walukuba.html")
    print("  - docs/kihihi.html")
