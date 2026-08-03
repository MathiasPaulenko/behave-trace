function traceViewer() {
    return {
        // ─── State ───
        trace: null,
        filter: 'all',
        currentScenario: null,
        selectedStepIdx: null,
        activeTab: 'screenshot',
        cursorPos: 0,
        snapshotMode: 'after',  // 'before' | 'after' (Playwright-style)

        // ─── Init ───
        async init() {
            try {
                const resp = await fetch('/api/trace');
                this.trace = await resp.json();
                // Initialize _open state on original feature objects
                this.trace.features.forEach(f => { f._open = true; });
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
            }
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

        // ─── Computed: filtered features ───
        get filteredFeatures() {
            if (!this.trace) return [];
            // Return original feature objects (with _open state set in init)
            // Do NOT spread — spreading creates copies and breaks _open state
            return this.trace.features;
        },

        // ─── Filtering ───
        filteredScenarios(feature) {
            if (this.filter === 'all') return feature.scenarios;
            if (this.filter === 'failed') {
                return feature.scenarios.filter(s => s.status === 'failed');
            }
            if (this.filter === 'slow') {
                return feature.scenarios.filter(s => s.duration > 0.5);
            }
            return feature.scenarios;
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
            if (this.snapshotMode === 'before' && this.hasBeforeSnapshot()) {
                const prevStep = this.currentScenario.steps[this.selectedStepIdx - 1];
                const dom = prevStep.artifacts?.find(a => a.type === 'dom');
                return dom?.text || '<p>No before snapshot</p>';
            }
            const dom = this.selectedStep.artifacts?.find(a => a.type === 'dom');
            return dom?.text || '<p>No snapshot available</p>';
        },

        // ─── Source (step implementation) ───
        sourcePath() {
            if (!this.selectedStep?.location) return '';
            return this.selectedStep.location;
        },

        sourceCode() {
            if (!this.selectedStep?.location) return 'No source location available.';
            return `# ${this.selectedStep.location}\n# Step: ${this.selectedStep.keyword} ${this.selectedStep.name}\n\n# Source loading via /api/source endpoint (future feature)`;
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
