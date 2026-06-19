document.addEventListener('DOMContentLoaded', () => {
  let cy = null;
  let rawGraph = null;
  let buildMetadata = null;
  let activeFilters = {
    kinds: new Set(),
    layers: new Set(),
    community: 'all'
  };

  // UI Elements
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const searchInput = document.getElementById('search-input');
  const searchResults = document.getElementById('search-results');
  const filterCommunity = document.getElementById('filter-community');
  const applyFiltersBtn = document.getElementById('apply-filters-btn');
  const tracePathBtn = document.getElementById('trace-path-btn');
  const clearPathBtn = document.getElementById('clear-path-btn');
  const pathSource = document.getElementById('path-source');
  const pathTarget = document.getElementById('path-target');
  const pathResult = document.getElementById('path-result');
  const detailsPanel = document.getElementById('details-panel');
  const detailsContent = document.getElementById('details-content');
  const detailsClose = document.getElementById('details-close');
  
  // Graph control buttons
  const ctrlFit = document.getElementById('ctrl-fit');
  const ctrlLayout = document.getElementById('ctrl-layout');
  const ctrlIncoming = document.getElementById('ctrl-incoming');
  const ctrlOutgoing = document.getElementById('ctrl-outgoing');

  // Category Colors matching CSS
  const colors = {
    'module': '#4f46e5',
    'class': '#0891b2',
    'function': '#0d9488',
    'variable': '#ea580c',
    'export': '#e11d48',
    'config': '#d97706',
    'external': '#4b5563',
    'default': '#9ca3af'
  };

  // Initialize navigation tabs
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
  });

  // Fetch all graph data and reports
  async function loadData() {
    try {
      const graphRes = await fetch('data/graph.json');
      if (!graphRes.ok) throw new Error('Graph data not found');
      rawGraph = await graphRes.json();

      // Attempt to load metadata and reports
      try {
        const metaRes = await fetch('data/build-metadata.json');
        if (metaRes.ok) buildMetadata = await metaRes.json();
      } catch (e) { console.warn('Metadata not loaded', e); }

      initializeDashboard();
    } catch (err) {
      console.error(err);
      alert('Failed to load graph data. Make sure to run the build script first!');
    }
  }

  // Determine Layer by node ID
  function getNodeLayer(id) {
    if (id.startsWith('config:')) return 'configuration';
    const lower = id.toLowerCase();
    if (lower.includes('test_') || lower.includes('.tests')) return 'tests';
    if (lower.includes('migrate_') || lower.includes('alembic')) return 'migrations';
    if (lower.includes('scripts/')) return 'scripts';
    if (lower.includes('apps.web') || lower.includes('apps/web')) return 'frontend';
    if (lower.includes('apps.api') || lower.includes('apps/api') || lower.includes('config.settings')) return 'backend';
    return 'backend';
  }

  // Populate UI & Cytoscape
  function initializeDashboard() {
    // 1. Setup stats
    const nodes = rawGraph.nodes || [];
    const edges = rawGraph.links || rawGraph.edges || [];
    
    document.getElementById('stat-nodes').textContent = nodes.length;
    document.getElementById('stat-edges').textContent = edges.length;

    // Determine communities count
    const communities = new Set();
    nodes.forEach(n => { if (n.community !== undefined) communities.add(n.community); });
    document.getElementById('stat-communities').textContent = communities.size || '-';

    // Populate community dropdown
    Array.from(communities).sort((a,b)=>a-b).forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = `Community ${c}`;
      filterCommunity.appendChild(opt);
    });

    // Setup metadata
    if (buildMetadata) {
      document.getElementById('profile-badge').textContent = buildMetadata.graph_profile === 'repository' ? 'Repository Architecture' : 'Code Architecture';
      document.getElementById('meta-sha').textContent = buildMetadata.repository_sha ? buildMetadata.repository_sha.substring(0, 7) : '-';
      document.getElementById('meta-version').textContent = buildMetadata.graphify_version || '-';
      document.getElementById('meta-time').textContent = buildMetadata.build_timestamp ? new Date(buildMetadata.build_timestamp).toLocaleString() : '-';
      document.getElementById('meta-status').textContent = buildMetadata.validation_status || '-';
      document.getElementById('stat-sccs').textContent = buildMetadata.strongly_connected_component_count || '-';
    }

    // 2. Prepare Cytoscape nodes & edges format
    const cyNodes = nodes.map(n => {
      const id = n.id;
      const type = n.type || 'module';
      const label = id.split(':').slice(1).join(':'); // show FQN label without kind
      const shortName = label.split('.').pop();
      return {
        data: {
          id: id,
          label: shortName,
          fqn: label,
          kind: type,
          layer: getNodeLayer(id),
          community: n.community || 0,
          file: n.file || ''
        }
      };
    });

    const cyEdges = edges.map((e, idx) => {
      return {
        data: {
          id: `edge-${idx}`,
          source: e.source.id || e.source,
          target: e.target.id || e.target,
          relation: e.relation || 'imports'
        }
      };
    });

    // 3. Initialize Cytoscape
    cy = cytoscape({
      container: document.getElementById('cy-container'),
      elements: { nodes: cyNodes, edges: cyEdges },
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'background-color': ele => colors[ele.data('kind')] || colors.default,
            'color': '#f3f4f6',
            'font-size': '10px',
            'font-family': 'var(--font-sans)',
            'width': '18px',
            'height': '18px',
            'text-valign': 'bottom',
            'text-margin-y': '4px',
            'text-wrap': 'ellipsis',
            'text-max-width': '80px',
            'overlay-opacity': 0,
            'transition-property': 'background-color, line-color, target-arrow-color, opacity',
            'transition-duration': '0.2s'
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': '3px',
            'border-color': '#60a5fa',
            'width': '24px',
            'height': '24px',
            'font-size': '12px',
            'font-weight': 'bold'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#3b82f6',
            'target-arrow-color': '#3b82f6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8,
            'opacity': 0.25,
            'overlay-opacity': 0
          }
        },
        {
          selector: 'edge[relation="contains"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#4b5563',
            'target-arrow-shape': 'none',
            'opacity': 0.15
          }
        },
        {
          selector: 'edge[relation="references_code"]',
          style: {
            'line-style': 'dotted',
            'line-color': '#d97706',
            'target-arrow-color': '#d97706',
            'target-arrow-shape': 'triangle',
            'opacity': 0.3
          }
        },
        // Highlighting classes
        {
          selector: '.highlighted',
          style: {
            'opacity': 1.0,
            'width': ele => ele.isNode() ? '22px' : 3.0,
            'height': ele => ele.isNode() ? '22px' : 3.0,
            'line-color': '#60a5fa',
            'target-arrow-color': '#60a5fa',
            'z-index': 9999
          }
        },
        {
          selector: '.dimmed',
          style: {
            'opacity': 0.05
          }
        }
      ],
      layout: {
        name: 'cose',
        idealEdgeLength: 50,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0
      }
    });

    // Setup Event Listeners
    setupGraphEvents();
    loadReportMetrics();
  }

  function setupGraphEvents() {
    // Click Node
    cy.on('tap', 'node', function(evt) {
      const node = evt.target;
      selectNode(node);
    });

    // Click Background -> reset highlights
    cy.on('tap', function(evt) {
      if (evt.target === cy) {
        resetHighlights();
        detailsPanel.style.display = 'none';
      }
    });

    // Sidebar Node Search
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase().trim();
      searchResults.innerHTML = '';
      if (!query) return;

      const matches = cy.nodes().filter(node => {
        return node.data('fqn').toLowerCase().includes(query);
      });

      matches.slice(0, 30).forEach(node => {
        const li = document.createElement('li');
        li.textContent = node.data('fqn');
        li.addEventListener('click', () => {
          cy.center(node);
          cy.select(node);
          selectNode(node);
        });
        searchResults.appendChild(li);
      });
    });

    // Apply Filters Action
    applyFiltersBtn.addEventListener('click', () => {
      const selectedKinds = Array.from(document.querySelectorAll('.filter-kind:checked')).map(cb => cb.value);
      const selectedLayers = Array.from(document.querySelectorAll('.filter-layer:checked')).map(cb => cb.value);
      const selectedCommunity = filterCommunity.value;

      cy.batch(() => {
        cy.nodes().forEach(node => {
          const kindMatch = selectedKinds.includes(node.data('kind'));
          const layerMatch = selectedLayers.includes(node.data('layer'));
          const commMatch = (selectedCommunity === 'all' || node.data('community').toString() === selectedCommunity);

          if (kindMatch && layerMatch && commMatch) {
            node.style('display', 'element');
          } else {
            node.style('display', 'none');
          }
        });
      });
    });

    // Control buttons
    ctrlFit.addEventListener('click', () => cy.fit());
    ctrlLayout.addEventListener('click', () => {
      cy.layout({ name: 'cose', randomize: false, fit: true }).run();
    });
    
    detailsClose.addEventListener('click', () => {
      detailsPanel.style.display = 'none';
    });

    // Path Tracer button
    tracePathBtn.addEventListener('click', () => {
      const srcQuery = pathSource.value.trim();
      const trgQuery = pathTarget.value.trim();
      if (!srcQuery || !trgQuery) return;

      const srcNode = cy.nodes().filter(n => n.data('fqn') === srcQuery || n.data('id') === srcQuery)[0];
      const trgNode = cy.nodes().filter(n => n.data('fqn') === trgQuery || n.data('id') === trgQuery)[0];

      if (!srcNode || !trgNode) {
        pathResult.innerHTML = `<div style="color:#ef4444;">Source or Target node not found.</div>`;
        return;
      }

      // Run BFS to find path
      const bfs = cy.elements().bfs({
        roots: srcNode,
        directed: true
      });

      const path = bfs.path.to(trgNode);
      if (path.length === 0) {
        pathResult.innerHTML = `<div style="color:#ef4444;">No dependency path found between the nodes.</div>`;
        return;
      }

      // Highlight path
      cy.elements().addClass('dimmed').removeClass('highlighted');
      path.addClass('highlighted').removeClass('dimmed');

      // Render steps
      pathResult.innerHTML = `<h4>Path steps (${Math.floor((path.length + 1)/2)} steps):</h4>`;
      let stepIdx = 1;
      path.nodes().forEach(n => {
        const stepDiv = document.createElement('div');
        stepDiv.className = 'path-step';
        stepDiv.textContent = `${stepIdx++}. ${n.data('fqn')}`;
        pathResult.appendChild(stepDiv);
      });
    });

    clearPathBtn.addEventListener('click', () => {
      resetHighlights();
      pathSource.value = '';
      pathTarget.value = '';
      pathResult.innerHTML = '';
    });
  }

  // Node highlight / detail presentation
  function selectNode(node) {
    cy.elements().removeClass('highlighted').addClass('dimmed');
    node.addClass('highlighted').removeClass('dimmed');

    // Highlight immediate neighborhood
    const neighborhood = node.neighborhood();
    neighborhood.addClass('highlighted').removeClass('dimmed');

    // Compute details
    const id = node.data('id');
    const fqn = node.data('fqn');
    const kind = node.data('kind');
    const layer = node.data('layer');
    const community = node.data('community');
    const file = node.data('file');

    const incoming = node.incomers('edge');
    const outgoing = node.outgoers('edge');

    // Check for validation warnings
    let warningHtml = '';
    if (id === 'class:apps.api.scripts.dev_db.Config') {
      warningHtml = `<div style="color:#eab308;margin-top:10px;font-weight:600;">⚠️ Known Collision Node: This is the Alembic Config class, distinct from application settings.</div>`;
    }

    detailsContent.innerHTML = `
      <p><strong>Fully Qualified ID:</strong> <span class="mono">${id}</span></p>
      <p><strong>Kind:</strong> <span class="badge" style="background-color:${colors[kind]}">${kind}</span></p>
      <p><strong>Layer:</strong> <span class="badge">${layer}</span></p>
      <p><strong>Community:</strong> ${community}</p>
      <p><strong>File Path:</strong> <span class="mono">${file || 'external'}</span></p>
      
      ${warningHtml}

      <h4>Metrics</h4>
      <p><strong>Fan-In (In-Degree):</strong> ${incoming.length}</p>
      <p><strong>Fan-Out (Out-Degree):</strong> ${outgoing.length}</p>

      <h4>Incoming Dependencies (${incoming.length})</h4>
      <ul>
        ${incoming.map(e => `<li>${e.source().data('fqn')}</li>`).join('') || '<li>None</li>'}
      </ul>

      <h4>Outgoing Dependencies (${outgoing.length})</h4>
      <ul>
        ${outgoing.map(e => `<li>${e.target().data('fqn')}</li>`).join('') || '<li>None</li>'}
      </ul>
    `;
    detailsPanel.style.display = 'flex';
  }

  function resetHighlights() {
    if (cy) cy.elements().removeClass('dimmed').removeClass('highlighted');
  }

  // Load computed reports dynamically
  async function loadReportMetrics() {
    const reportFiles = [
      { id: 'top-fan-in.json', el: 'rank-fan-in', list: true, prefix: 'Fan-In' },
      { id: 'top-fan-out.json', el: 'rank-fan-out', list: true, prefix: 'Fan-Out' },
      { id: 'orphan-symbols.json', el: 'rank-orphans', list: true, prefix: 'Degree' },
      { id: 'strongly-connected-components.json', el: 'cycle-list', list: true, prefix: 'SCC Size', scc: true },
      { id: 'ambiguous-symbols.json', el: 'ambiguous-list', list: true, prefix: 'Matches', desc: 'ambiguous' },
      { id: 'unresolved-imports.json', el: 'unresolved-list', list: true, prefix: 'Source', desc: 'unresolved' },
      { id: 'boundary-violations.json', el: 'violations-list', list: true, prefix: 'Type', desc: 'violation' }
    ];

    for (const rep of reportFiles) {
      const domEl = document.getElementById(rep.el);
      if (!domEl) continue;

      try {
        const res = await fetch(`data/${rep.id}`);
        if (!res.ok) continue;
        const data = await res.json();

        domEl.innerHTML = '';
        if (data.length === 0) {
          domEl.innerHTML = '<li>None detected.</li>';
          continue;
        }

        // Cycle count summary
        if (rep.scc) {
          const cycles = data.filter(c => c.size > 1);
          document.getElementById('cycle-summary').textContent = `${cycles.length} dependency cycle components found.`;
        }

        data.slice(0, 15).forEach(item => {
          const li = document.createElement('li');
          
          if (rep.scc) {
            li.textContent = `SCC (Size ${item.size}): ${item.nodes.slice(0,3).join(', ')}${item.nodes.length > 3 ? '...' : ''}`;
            li.style.cursor = 'pointer';
            li.addEventListener('click', () => {
              // Highlight the cycle component
              cy.elements().addClass('dimmed').removeClass('highlighted');
              const sccNodes = cy.nodes().filter(n => item.nodes.includes(n.data('id')) || item.nodes.includes(n.data('fqn')));
              sccNodes.addClass('highlighted').removeClass('dimmed');
              sccNodes.connectedEdges().addClass('highlighted').removeClass('dimmed');
            });
          } else if (rep.desc === 'ambiguous') {
            li.textContent = `FQN: ${item.import} in ${item.file}`;
          } else if (rep.desc === 'unresolved') {
            li.textContent = `Import '${item.import}' in file ${item.file}`;
          } else if (rep.desc === 'violation') {
            li.textContent = `${item.source} -> ${item.target} (${item.reason})`;
          } else {
            // Rankings
            const fqn = item.node.split(':').slice(1).join(':');
            li.textContent = `${fqn} (${rep.prefix}: ${item.value})`;
            li.addEventListener('click', () => {
              const node = cy.nodes().filter(n => n.data('id') === item.node)[0];
              if (node) {
                cy.center(node);
                cy.select(node);
                selectNode(node);
              }
            });
          }
          domEl.appendChild(li);
        });

        if (data.length > 15) {
          const li = document.createElement('li');
          li.className = 'placeholder-text';
          li.textContent = `Showing 15 of ${data.length} items...`;
          domEl.appendChild(li);
        }
      } catch (e) {
        console.warn(`Report data/${rep.id} could not be loaded`, e);
        domEl.innerHTML = '<li>Report data absent.</li>';
      }
    }
  }

  loadData();
});
