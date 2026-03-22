# Agri-Direct

A web application for managing agricultural cooperative inventory and harvest data.

## Features

- User registration and authentication
- Dashboard with inventory overview
- CSV upload for harvest data
- REST API for external integrations
- Responsive design with Bootstrap

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv .venv`
3. Activate the virtual environment: `.venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run the application: `python app.py`

## Usage

- Default login: username `admin`, password `admin`
- Register a new account or login
- Upload CSV files with harvest data (columns: crop_name, quantity)
- View inventory and summaries on the dashboard
- Use the API endpoint `/api/harvest` with API key for external submissions

## API

POST /api/harvest
Headers: x-api-key: your_api_key
Body: {"crop_name": "wheat", "quantity": 100, "farmer": "John"}

## Environment Variables

- SECRET_KEY: Flask secret key
- API_KEY: API key for REST endpoint