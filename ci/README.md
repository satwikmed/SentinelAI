CI workflow lives at ci/ci-eval.yml until the GitHub token has `workflow` scope.
Then: mkdir -p .github/workflows && git mv ci/ci-eval.yml .github/workflows/ci-eval.yml && git commit -am "Restore GitHub Actions workflow" && git push
