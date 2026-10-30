name: Auto Update Egypt GeoJSON Datasets

on:
  schedule:
    # يعمل تلقائياً كل 3 أيام الساعة 12 منتصف الليل (00:00 UTC)
    - cron: '0 0 */3 * *'
  workflow_dispatch:

jobs:
  update-datasets:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          persist-credentials: true

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Fetch Latest Data from Overpass Turbo API
        run: |
          python update_geojson.py

      - name: Commit and Push Updated Datasets
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add radars.geojson speed_bumps.geojson fuel.geojson hospital.geojson version.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "Auto-update GeoJSON datasets from Overpass API [skip ci]" && git push)
