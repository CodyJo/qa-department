.PHONY: setup qa fix watch dashboard clean help jobs
.PHONY: seo ada compliance monetization product audit-all audit-all-parallel audit-live full-scan quick-sync
.PHONY: grafana grafana-stop grafana-logs

TARGET ?=

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Initial setup (create configs, check prerequisites)
	bash scripts/setup.sh

# ── QA Department ─────────────────────────────────────────────────────────────

qa: ## Run QA scan on TARGET repo (make qa TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make qa TARGET=/path/to/repo" && exit 1)
	bash agents/qa-scan.sh "$(TARGET)"

fix: ## Run fix agent on TARGET repo (make fix TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make fix TARGET=/path/to/repo" && exit 1)
	bash agents/fix-bugs.sh "$(TARGET)"

watch: ## Watch for new findings and auto-fix (make watch TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make watch TARGET=/path/to/repo" && exit 1)
	bash agents/watch.sh "$(TARGET)" --auto-fix --sync

scan-and-fix: ## Run full cycle: scan then fix (make scan-and-fix TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make scan-and-fix TARGET=/path/to/repo" && exit 1)
	bash agents/qa-scan.sh "$(TARGET)" --sync
	bash agents/fix-bugs.sh "$(TARGET)" --sync

# ── SEO Department ────────────────────────────────────────────────────────────

seo: ## Run SEO audit on TARGET repo (make seo TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make seo TARGET=/path/to/repo" && exit 1)
	bash agents/seo-audit.sh "$(TARGET)"

# ── ADA Compliance ────────────────────────────────────────────────────────────

ada: ## Run ADA compliance audit on TARGET repo (make ada TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make ada TARGET=/path/to/repo" && exit 1)
	bash agents/ada-audit.sh "$(TARGET)"

# ── Regulatory Compliance ─────────────────────────────────────────────────────

compliance: ## Run compliance audit on TARGET (make compliance TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make compliance TARGET=/path/to/repo" && exit 1)
	bash agents/compliance-audit.sh "$(TARGET)"

# ── Monetization Department ───────────────────────────────────────────────────

monetization: ## Run monetization audit on TARGET (make monetization TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make monetization TARGET=/path/to/repo" && exit 1)
	bash agents/monetization-audit.sh "$(TARGET)"

# ── Product Roadmap Department ────────────────────────────────────────────────

product: ## Run product roadmap audit on TARGET (make product TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make product TARGET=/path/to/repo" && exit 1)
	bash agents/product-audit.sh "$(TARGET)"

# ── Company-Wide ──────────────────────────────────────────────────────────────

audit-all: ## Run ALL audits sequentially on TARGET repo
	@test -n "$(TARGET)" || (echo "Usage: make audit-all TARGET=/path/to/repo" && exit 1)
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║  BreakPoint Labs — Full Company Audit                    ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Running all department audits on: $(TARGET)"
	@echo "Progress: http://localhost:8070/jobs.html"
	@echo ""
	bash scripts/job-status.sh init "$(TARGET)" "qa seo ada compliance monetization product"
	bash agents/qa-scan.sh "$(TARGET)" --sync
	bash agents/seo-audit.sh "$(TARGET)" --sync
	bash agents/ada-audit.sh "$(TARGET)" --sync
	bash agents/compliance-audit.sh "$(TARGET)" --sync
	bash agents/monetization-audit.sh "$(TARGET)" --sync
	bash agents/product-audit.sh "$(TARGET)" --sync
	bash scripts/job-status.sh finalize
	bash scripts/sync-dashboard.sh 2>/dev/null || true
	@echo ""
	@echo "All audits complete. Dashboard deployed."

audit-all-parallel: ## Run ALL audits in parallel (2 waves of 3)
	@test -n "$(TARGET)" || (echo "Usage: make audit-all-parallel TARGET=/path/to/repo" && exit 1)
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║  BreakPoint Labs — Full Company Audit (Parallel)         ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Running all department audits in parallel on: $(TARGET)"
	@echo "Progress: http://localhost:8070/jobs.html"
	@echo ""
	bash scripts/job-status.sh init "$(TARGET)" "qa seo ada compliance monetization product"
	bash agents/qa-scan.sh "$(TARGET)" --sync & \
	bash agents/seo-audit.sh "$(TARGET)" --sync & \
	bash agents/ada-audit.sh "$(TARGET)" --sync & \
	wait
	bash agents/compliance-audit.sh "$(TARGET)" --sync & \
	bash agents/monetization-audit.sh "$(TARGET)" --sync & \
	bash agents/product-audit.sh "$(TARGET)" --sync & \
	wait
	bash scripts/job-status.sh finalize
	bash scripts/sync-dashboard.sh 2>/dev/null || true
	@echo ""
	@echo "All audits complete. Dashboard deployed."

full-scan: ## Run all audits + auto-fix (make full-scan TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make full-scan TARGET=/path/to/repo" && exit 1)
	$(MAKE) audit-all TARGET="$(TARGET)"
	bash agents/fix-bugs.sh "$(TARGET)" --sync

audit-live: ## Run ALL audits with live dashboard refresh after each (make audit-live TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make audit-live TARGET=/path/to/repo" && exit 1)
	@REPO_NAME=$$(basename "$(TARGET)") && \
	echo "╔══════════════════════════════════════════════════════════╗" && \
	echo "║  BreakPoint Labs — Live Audit (auto-refresh dashboard)  ║" && \
	echo "╚══════════════════════════════════════════════════════════╝" && \
	echo "" && \
	echo "Target: $(TARGET)" && \
	echo "Repo:   $$REPO_NAME" && \
	echo "Dashboard updates live after each department completes." && \
	echo "" && \
	echo "── Deploying HTML dashboards ──" && \
	bash scripts/quick-sync.sh all "$$REPO_NAME" 2>/dev/null; \
	echo "" && \
	echo "── Wave 1: QA + SEO + ADA (parallel) ──" && \
	( bash agents/qa-scan.sh "$(TARGET)" && echo "  QA done — syncing..." && bash scripts/quick-sync.sh qa "$$REPO_NAME" ) & \
	( bash agents/seo-audit.sh "$(TARGET)" && echo "  SEO done — syncing..." && bash scripts/quick-sync.sh seo "$$REPO_NAME" ) & \
	( bash agents/ada-audit.sh "$(TARGET)" && echo "  ADA done — syncing..." && bash scripts/quick-sync.sh ada "$$REPO_NAME" ) & \
	wait && \
	echo "" && \
	echo "── Wave 2: Compliance + Monetization + Product (parallel) ──" && \
	( bash agents/compliance-audit.sh "$(TARGET)" && echo "  Compliance done — syncing..." && bash scripts/quick-sync.sh compliance "$$REPO_NAME" ) & \
	( bash agents/monetization-audit.sh "$(TARGET)" && echo "  Monetization done — syncing..." && bash scripts/quick-sync.sh monetization "$$REPO_NAME" ) & \
	( bash agents/product-audit.sh "$(TARGET)" && echo "  Product done — syncing..." && bash scripts/quick-sync.sh product "$$REPO_NAME" ) & \
	wait && \
	echo "" && \
	echo "All audits complete. Dashboard updated live at each step."

quick-sync: ## Quick-sync one department's data (make quick-sync DEPT=qa REPO=codyjo.com)
	bash scripts/quick-sync.sh "$(DEPT)" "$(REPO)"

# ── Dashboard & Infrastructure ────────────────────────────────────────────────

dashboard: ## Deploy all dashboards to S3
	bash scripts/sync-dashboard.sh

jobs: ## Start dashboard server with scan API (make jobs TARGET=/path/to/repo)
	python3 scripts/dashboard-server.py $(if $(TARGET),--target "$(TARGET)",)

grafana: ## Start Grafana monitoring dashboard
	cd monitoring && docker compose up -d
	@echo "Grafana running at http://localhost:3333 (admin / breakpoint)"

grafana-stop: ## Stop Grafana
	cd monitoring && docker compose down

grafana-logs: ## Tail Grafana logs
	cd monitoring && docker compose logs -f grafana

clean: ## Remove all results
	rm -rf results/*/
	rm -f dashboard/data.json dashboard/qa-data.json dashboard/seo-data.json dashboard/ada-data.json dashboard/compliance-data.json dashboard/monetization-data.json dashboard/product-data.json
	@echo "Results cleaned."
