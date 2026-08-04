function traceViewer() {
    return {
        // ─── State ───
        trace: null,
        filter: 'all',
        searchQuery: '',
        statusFilters: { passed: false, failed: false, skipped: false, undefined: false },
        selectedTags: [],
        currentScenario: null,
        selectedStepIdx: null,
        activeTab: 'screenshot',
        selectedNetworkIdx: null,
        cursorPos: 0,
        snapshotMode: 'after',  // 'before' | 'after' (Playwright-style)
        sourceData: null,       // fetched source snippet from /api/source
        sourceLoading: false,
        isWatching: false,
        isRunning: false,
        selectedScenarios: [],
        _eventSource: null,
        theme: 'dark',          // 'dark' | 'light'
        sidebarCollapsed: false,
        isLoading: false,
        traceLoaded: false,
        copyFeedback: false,

        // ─── Init ───
        async init() {
            // Load saved theme
            const savedTheme = localStorage.getItem('bt-theme');
            if (savedTheme === 'light' || savedTheme === 'dark') {
                this.theme = savedTheme;
            }
            this._applyTheme();

            this.isLoading = true;
            try {
                const resp = await fetch('/api/trace');
                this.trace = await resp.json();
                this.traceLoaded = true;
                // Initialize _open state on original feature objects
                this.trace.features.forEach(f => { f._open = true; });
                // Check if watch mode is active
                try {
                    const watchResp = await fetch('/api/watching');
                    const watchData = await watchResp.json();
                    this.isWatching = watchData.watching === true;
                } catch {
                    // Endpoint may not exist in older servers
                }
                // Connect to SSE stream for live updates
                this._connectSSE();
                // Auto-open first failed scenario (Playwright does this)
                const firstFailed = this.allScenarios.find(s => s.status === 'failed');
                if (firstFailed) {
                    this.selectScenario(firstFailed);
                } else if (this.allScenarios.length > 0) {
                    // Fallback: select first scenario if no failures
                    this.selectScenario(this.allScenarios[0]);
                }
            } catch (err) {
                console.error('Failed to load trace:', err);
            } finally {
                this.isLoading = false;
            }
        },

        // ─── SSE live updates ───
        _connectSSE() {
            if (this._eventSource) return;
            try {
                this._eventSource = new EventSource('/api/stream');
                this._eventSource.onmessage = (e) => {
                    try {
                        const event = JSON.parse(e.data);
                        this._handleSSEEvent(event);
                    } catch {
                        // Ignore malformed events
                    }
                };
                this._eventSource.onerror = () => {
                    // Will auto-reconnect; just log
                    console.warn('SSE connection error, will reconnect...');
                };
            } catch {
                // EventSource not available or server doesn't support it
            }
        },

        _handleSSEEvent(event) {
            switch (event.type) {
                case 'state':
                    this.isRunning = event.running === true;
                    if (event.watching !== undefined) {
                        this.isWatching = event.watching === true;
                    }
                    break;
                case 'run_started':
                    this.isRunning = true;
                    break;
                case 'run_completed':
                    this.isRunning = false;
                    break;
                case 'trace_updated':
                    this._reloadTrace();
                    break;
            }
        },

        async _reloadTrace() {
            try {
                const resp = await fetch('/api/trace');
                const newTrace = await resp.json();
                // Preserve _open state from current features
                const openMap = {};
                if (this.trace) {
                    this.trace.features.forEach(f => { openMap[f.name] = f._open; });
                }
                newTrace.features.forEach(f => {
                    f._open = openMap[f.name] !== undefined ? openMap[f.name] : true;
                });
                this.trace = newTrace;
            } catch (err) {
                console.error('Failed to reload trace:', err);
            }
        },

        async rerunFailed() {
            if (this.isRunning) return;
            const failedNames = this.allScenarios
                .filter(s => s.status === 'failed')
                .map(s => s.name);
            if (failedNames.length === 0) return;
            try {
                await fetch('/api/rerun', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filter: 'failed', scenarios: failedNames }),
                });
            } catch (err) {
                console.error('Re-run failed:', err);
            }
        },

        async runSelected() {
            if (this.isRunning) return;
            if (this.selectedScenarios.length === 0) return;
            try {
                await fetch('/api/rerun', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filter: 'failed', scenarios: this.selectedScenarios }),
                });
            } catch (err) {
                console.error('Run selected failed:', err);
            }
        },

        toggleScenarioSelection(name) {
            const idx = this.selectedScenarios.indexOf(name);
            if (idx >= 0) {
                this.selectedScenarios.splice(idx, 1);
            } else {
                this.selectedScenarios.push(name);
            }
        },

        isScenarioSelected(name) {
            return this.selectedScenarios.includes(name);
        },

        selectAllScenarios() {
            this.selectedScenarios = this.allScenarios.map(s => s.name);
        },

        deselectAllScenarios() {
            this.selectedScenarios = [];
        },

        selectFailedScenarios() {
            this.selectedScenarios = this.allScenarios
                .filter(s => s.status === 'failed')
                .map(s => s.name);
        },

        // ─── Keyboard navigation ───
        handleKeydown(e) {
            // Don't interfere with text inputs
            const tag = e.target.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA') return;

            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                if (!this.currentScenario) return;
                const steps = this.currentScenario.steps;
                if (steps.length === 0) return;
                let idx = this.selectedStepIdx ?? -1;
                if (e.key === 'ArrowDown') {
                    idx = Math.min(idx + 1, steps.length - 1);
                } else {
                    idx = Math.max(idx - 1, 0);
                }
                this.selectStep(idx);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                // Enter on tree: expand/collapse current scenario's feature
                if (this.currentScenario) {
                    const feature = this.trace.features.find(f =>
                        f.scenarios.includes(this.currentScenario)
                    );
                    if (feature) this.toggleFeature(feature);
                }
            } else if (e.key === 'n') {
                // 'n' toggles sidebar
                this.toggleSidebar();
            }
        },

        // ─── Copy step info ───
        async copyStepInfo() {
            if (!this.selectedStep) return;
            const step = this.selectedStep;
            const info = `${step.keyword} ${step.name}\nLocation: ${step.location || 'N/A'}\nStatus: ${step.status}\nDuration: ${this.formatDuration(step.duration)}`;
            try {
                await navigator.clipboard.writeText(info);
                this.copyFeedback = true;
                setTimeout(() => { this.copyFeedback = false; }, 2000);
            } catch (err) {
                console.error('Copy failed:', err);
            }
        },

        // ─── Export trace ───
        exportTrace() {
            if (!this.trace) return;
            const blob = new Blob([JSON.stringify(this.trace, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'behave-trace.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },

        // ─── Theme toggle ───
        toggleTheme() {
            this.theme = this.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('bt-theme', this.theme);
            this._applyTheme();
        },

        _applyTheme() {
            document.documentElement.setAttribute('data-theme', this.theme);
        },

        // ─── Sidebar toggle ───
        toggleSidebar() {
            this.sidebarCollapsed = !this.sidebarCollapsed;
        },

        // ─── Computed: stats ───
        get stats() {
            if (!this.trace) {
                return {
                    passed: 0, failed: 0, skipped: 0,
                    totalScenarios: 0, totalSteps: 0,
                    totalScreenshots: 0, duration: 0,
                    slowestStep: 0,
                };
            }
            const s = this.trace.stats || {};
            return {
                passed: s.by_status?.passed || 0,
                failed: s.by_status?.failed || 0,
                skipped: s.by_status?.skipped || 0,
                totalScenarios: s.total_scenarios || 0,
                totalSteps: s.total_steps || 0,
                totalScreenshots: s.total_screenshots || 0,
                duration: s.duration || 0,
                slowestStep: s.slowest_step_duration || 0,
            };
        },

        // ─── Computed: all scenarios (flat list) ───
        get allScenarios() {
            if (!this.trace) return [];
            return this.trace.features.flatMap(f => f.scenarios);
        },

        // ─── Computed: all tags ───
        get allTags() {
            if (!this.trace) return [];
            const tags = new Set();
            this.trace.features.forEach(f => {
                (f.tags || []).forEach(t => tags.add(t));
                f.scenarios.forEach(s => {
                    (s.tags || []).forEach(t => tags.add(t));
                });
            });
            return Array.from(tags).sort();
        },

        // ─── Computed: filtered features ───
        get filteredFeatures() {
            if (!this.trace) return [];
            // Hide features that have zero matching scenarios
            return this.trace.features.filter(f => this.filteredScenarios(f).length > 0);
        },

        // ─── Filtering ───
        matchesSearch(scenario) {
            if (!this.searchQuery) return true;
            const q = this.searchQuery.toLowerCase();
            if (scenario.name.toLowerCase().includes(q)) return true;
            if (scenario.tags?.some(t => t.toLowerCase().includes(q))) return true;
            if (scenario.feature_name?.toLowerCase().includes(q)) return true;
            return false;
        },

        matchesStatusFilter(scenario) {
            // If no status checkboxes are checked, show all
            const anyChecked = Object.values(this.statusFilters).some(v => v);
            if (!anyChecked) return true;
            return this.statusFilters[scenario.status] === true;
        },

        matchesTags(scenario) {
            if (this.selectedTags.length === 0) return true;
            return this.selectedTags.some(t => scenario.tags?.includes(t));
        },

        matchesRadioFilter(scenario) {
            if (this.filter === 'all') return true;
            if (this.filter === 'failed') return scenario.status === 'failed';
            if (this.filter === 'slow') return (scenario.duration || 0) > 0.5;
            return true;
        },

        filteredScenarios(feature) {
            return feature.scenarios.filter(s =>
                this.matchesSearch(s) &&
                this.matchesStatusFilter(s) &&
                this.matchesTags(s) &&
                this.matchesRadioFilter(s)
            );
        },

        toggleTag(tag) {
            const idx = this.selectedTags.indexOf(tag);
            if (idx >= 0) {
                this.selectedTags.splice(idx, 1);
            } else {
                this.selectedTags.push(tag);
            }
        },

        clearFilters() {
            this.searchQuery = '';
            this.filter = 'all';
            this.statusFilters = { passed: false, failed: false, skipped: false, undefined: false };
            this.selectedTags = [];
        },

        get hasActiveFilters() {
            return this.searchQuery !== '' ||
                this.filter !== 'all' ||
                this.selectedTags.length > 0 ||
                Object.values(this.statusFilters).some(v => v);
        },

        // ─── Highlight matched text ───
        highlightText(text) {
            if (!text) return '';
            // Escape HTML to prevent XSS
            const escapedText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
            if (!this.searchQuery) return escapedText;
            const q = this.searchQuery.trim();
            if (!q) return escapedText;
            const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp('(' + escaped + ')', 'gi');
            return escapedText.replace(regex, '<mark>$1</mark>');
        },

        // ─── Tree interactions ───
        toggleFeature(feature) {
            feature._open = !feature._open;
        },

        isActiveScenario(scenario) {
            return this.currentScenario === scenario;
        },

        // ─── Selection ───
        selectScenario(scenario) {
            this.currentScenario = scenario;
            this.selectedStepIdx = null;
            this.activeTab = 'screenshot';
            this.cursorPos = 0;
            // Auto-select first failed step, or first step (Playwright behavior)
            const firstFailed = scenario.steps.findIndex(s => s.status === 'failed');
            if (firstFailed >= 0) {
                this.selectStep(firstFailed);
            } else if (scenario.steps.length > 0) {
                // Fallback: select first step if no failures
                this.selectStep(0);
            }
        },

        selectStep(idx) {
            this.selectedStepIdx = idx;
            const step = this.currentScenario?.steps[idx];
            if (!step) return;
            // Auto-select first available tab (Playwright priority order)
            if (step.has_screenshot) {
                this.activeTab = 'screenshot';
            } else if (step.has_dom) {
                this.activeTab = 'snapshot';
            } else if (step.location) {
                this.activeTab = 'source';
            } else if (step.logs?.length > 0) {
                this.activeTab = 'console';
            } else if (step.error) {
                this.activeTab = 'error';
            } else if (step.artifacts?.length > 0) {
                this.activeTab = 'artifacts';
            }
            // Update cursor position on timeline
            this.updateCursor();
            // Fetch source code for this step
            this.fetchSource();
        },

        get selectedStep() {
            if (this.selectedStepIdx === null || !this.currentScenario) return null;
            return this.currentScenario.steps[this.selectedStepIdx];
        },

        // ─── Timeline (Playwright-style scrubbing) ───
        segmentWidth(step) {
            const total = this.currentScenario?.duration || 1;
            return ((step.duration || 0) / total) * 100;
        },

        updateCursor() {
            if (!this.currentScenario || this.selectedStepIdx === null) {
                this.cursorPos = 0;
                return;
            }
            const total = this.currentScenario.duration || 1;
            let elapsed = 0;
            for (let i = 0; i < this.selectedStepIdx; i++) {
                elapsed += this.currentScenario.steps[i].duration || 0;
            }
            // Center cursor on the selected step
            const stepDuration = this.currentScenario.steps[this.selectedStepIdx].duration || 0;
            this.cursorPos = ((elapsed + stepDuration / 2) / total) * 100;
        },

        seekTo(event) {
            if (!this.currentScenario) return;
            const bar = event.currentTarget;
            const rect = bar.getBoundingClientRect();
            const ratio = (event.clientX - rect.left) / rect.width;
            const target = ratio * (this.currentScenario.duration || 0);
            // Find step at this time position
            let elapsed = 0;
            for (let i = 0; i < this.currentScenario.steps.length; i++) {
                elapsed += this.currentScenario.steps[i].duration || 0;
                if (elapsed >= target) {
                    this.selectStep(i);
                    return;
                }
            }
        },

        // ─── Snapshot (before/after, Playwright-style) ───
        hasBeforeSnapshot() {
            if (this.selectedStepIdx === null || !this.currentScenario) return false;
            if (this.selectedStepIdx === 0) return false;
            const prevStep = this.currentScenario.steps[this.selectedStepIdx - 1];
            return prevStep?.has_dom || false;
        },

        currentSnapshotHtml() {
            if (!this.selectedStep) return '<p>No snapshot available</p>';
            let html;
            if (this.snapshotMode === 'before' && this.hasBeforeSnapshot()) {
                const prevStep = this.currentScenario.steps[this.selectedStepIdx - 1];
                const dom = prevStep.artifacts?.find(a => a.type === 'dom');
                html = dom?.text || '<p>No before snapshot</p>';
            } else {
                const dom = this.selectedStep.artifacts?.find(a => a.type === 'dom');
                html = dom?.text || '<p>No snapshot available</p>';
            }
            // Strip <script> and <noscript> tags so the snapshot renders as a
            // static visual state without re-executing SPA JavaScript in the iframe
            return html.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<noscript[\s\S]*?<\/noscript>/gi, '');
        },

        // ─── Source (step implementation) ───
        sourcePath() {
            if (!this.selectedStep?.location) return '';
            return this.selectedStep.location;
        },

        async fetchSource() {
            const loc = this.selectedStep?.location;
            if (!loc) {
                this.sourceData = null;
                return;
            }
            // Parse "file.py:line" format
            const colonIdx = loc.lastIndexOf(':');
            if (colonIdx === -1) {
                this.sourceData = null;
                return;
            }
            const path = loc.substring(0, colonIdx);
            const line = loc.substring(colonIdx + 1);
            this.sourceLoading = true;
            try {
                const resp = await fetch(`/api/source?path=${encodeURIComponent(path)}&line=${encodeURIComponent(line)}`);
                if (resp.ok) {
                    this.sourceData = await resp.json();
                } else {
                    this.sourceData = null;
                }
            } catch (err) {
                console.error('Failed to load source:', err);
                this.sourceData = null;
            } finally {
                this.sourceLoading = false;
            }
        },

        get sourceCode() {
            if (this.sourceLoading) return 'Loading source...';
            if (!this.sourceData) return 'No source location available.';
            const lines = this.sourceData.snippet || [];
            return lines.map(l => {
                const prefix = l.highlight ? ' >>> ' : '     ';
                return prefix + String(l.number).padStart(4, ' ') + ' | ' + l.content;
            }).join('\n');
        },

        // ─── Computed: has screenshots (for filmstrip visibility) ───
        get hasScreenshots() {
            if (!this.currentScenario) return false;
            return this.currentScenario.steps.some(s => s.has_screenshot);
        },

        // ─── Artifact helpers ───
        screenshotArtifacts(step) {
            if (!step) return [];
            return step.artifacts?.filter(a => a.type === 'screenshot') || [];
        },

        networkArtifacts(step) {
            if (!step) return [];
            const arts = step.artifacts?.filter(a => a.type === 'network') || [];
            return arts.map(a => {
                try {
                    return JSON.parse(a.text || '{}');
                } catch {
                    return { method: '', url: a.name, status: null };
                }
            });
        },

        domArtifacts(step) {
            if (!step) return [];
            return step.artifacts?.filter(a => a.type === 'dom') || [];
        },

        thumbnailSrc(step) {
            const ss = step.artifacts?.find(a => a.type === 'screenshot');
            if (!ss) return '';
            return 'data:' + ss.mime_type + ';base64,' + ss.data_base64;
        },

        // ─── Formatting ───
        logLevel(line) {
            if (typeof line === 'object' && line !== null) return line.level || 'info';
            return 'info';
        },

        logMessage(line) {
            if (typeof line === 'object' && line !== null) return line.message || '';
            return String(line || '');
        },

        logTime(line) {
            if (typeof line === 'object' && line !== null && line.timestamp) {
                try {
                    return new Date(line.timestamp).toLocaleTimeString();
                } catch {
                    return '';
                }
            }
            return '';
        },

        formatDuration(seconds) {
            if (!seconds || seconds === 0) return '0ms';
            if (seconds < 1.0) return Math.round(seconds * 1000) + 'ms';
            if (seconds < 60.0) return seconds.toFixed(2) + 's';
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return m + 'm ' + s + 's';
        },

        formatTime(timestamp) {
            if (!timestamp) return '';
            try {
                const d = new Date(timestamp);
                return d.toLocaleTimeString();
            } catch {
                return '';
            }
        },
    };
}
