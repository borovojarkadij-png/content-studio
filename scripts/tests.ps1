Push-Location backend
python -m pytest -v
python -m ruff check src tests
Pop-Location
Push-Location frontend
npm run build
Pop-Location
