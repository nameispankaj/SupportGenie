# NavisLogix ERP — Shipping, Freight Forwarding & Logistics Management Web Application

## Architecture Overview
- **Frontend (`index.html`)**: HTML5, CSS3 (Tailwind CSS), Vanilla JavaScript, Chart.js, Font Awesome. Hosted on **GitHub Pages**.
- **Backend (`Code.gs`)**: **Google Apps Script** deployed as a Web App (`doGet` & `doPost` HTTP JSON API).
- **Database**: **Google Sheets** with 6 automated relational tabs (`Shipments`, `Customers`, `Bookings`, `Containers`, `Invoices_Payments`, `Audit_Log`).

## Quick Deployment Steps
1. Create a new Google Sheet and open **Extensions -> Apps Script**.
2. Paste `Code.gs` into the editor, save, and run `initializeDatabase()` once.
3. Click **Deploy -> New deployment -> Web app** (*Execute as: Me*, *Who has access: Anyone*) and copy the `/exec` URL.
4. Host `index.html` on **GitHub Pages** and paste your `/exec` URL in **Settings (#8)**.
