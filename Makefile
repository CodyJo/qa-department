.PHONY: setup qa fix watch dashboard clean help

TARGET ?=

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Initial setup (create configs, check prerequisites)
	bash scripts/setup.sh

qa: ## Run QA scan on TARGET repo (make qa TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make qa TARGET=/path/to/repo" && exit 1)
	bash agents/qa-scan.sh "$(TARGET)"

fix: ## Run fix agent on TARGET repo (make fix TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make fix TARGET=/path/to/repo" && exit 1)
	bash agents/fix-bugs.sh "$(TARGET)"

watch: ## Watch for new findings and auto-fix (make watch TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make watch TARGET=/path/to/repo" && exit 1)
	bash agents/watch.sh "$(TARGET)" --auto-fix --sync

dashboard: ## Deploy dashboard to S3
	bash scripts/sync-dashboard.sh

scan-and-fix: ## Run full cycle: scan then fix (make scan-and-fix TARGET=/path/to/repo)
	@test -n "$(TARGET)" || (echo "Usage: make scan-and-fix TARGET=/path/to/repo" && exit 1)
	bash agents/qa-scan.sh "$(TARGET)" --sync
	bash agents/fix-bugs.sh "$(TARGET)" --sync

clean: ## Remove all results
	rm -rf results/*/
	rm -f dashboard/data.json
	@echo "Results cleaned."
