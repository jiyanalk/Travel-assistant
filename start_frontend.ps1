Set-Location frontend

if (-not (Test-Path "node_modules")) {
    npm install
}

if (-not (Test-Path ".env.local") -and (Test-Path ".env.local.example")) {
    Copy-Item ".env.local.example" ".env.local"
}

npm run dev
