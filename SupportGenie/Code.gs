/**
 * ============================================================================
 * NAVISLOGIX ERP — GOOGLE APPS SCRIPT BACKEND API (Code.gs)
 * Complete Shipping, Freight Forwarding & Logistics Management System
 * Database: Google Sheets (6 Relational Tabs)
 * Communication: HTTP GET / POST JSON Web App API (GitHub Pages Compatible)
 * ============================================================================
 */

const DB_CONFIG = {
  APP_NAME: 'NavisLogix Shipping & Logistics ERP',
  VERSION: '2.4.0',
  SHEETS: {
    SHIPMENTS: 'Shipments',
    CUSTOMERS: 'Customers',
    BOOKINGS: 'Bookings',
    CONTAINERS: 'Containers',
    INVOICES: 'Invoices_Payments',
    AUDIT: 'Audit_Log'
  },
  HEADERS: {
    Shipments: [
      'shipmentId', 'shipmentRef', 'bookingRef', 'shipmentType', 'shipmentMode',
      'shipmentCategory', 'priority', 'shipmentStatus', 'shipperName', 'consigneeName',
      'notifyParty', 'customerId', 'customerName', 'contactPerson', 'email',
      'phone', 'billingParty', 'originCountry', 'originPort', 'originCity',
      'destCountry', 'destPort', 'destCity', 'placeOfReceipt', 'placeOfDelivery',
      'transshipmentPort', 'vesselName', 'voyageNumber', 'shippingLine', 'bookingDate',
      'cargoReadyDate', 'etd', 'atd', 'eta', 'ata',
      'deliveryDate', 'blNumber', 'masterBl', 'houseBl', 'awbNumber',
      'customsDeclarationNo', 'certificateNo', 'documentStatus', 'incoterms', 'paymentTerms',
      'insuranceRequired', 'insuranceAmount', 'specialInstructions', 'internalRemarks', 'updatedAt'
    ],
    Customers: [
      'customerId', 'customerCode', 'customerType', 'companyName', 'legalBusinessName',
      'gstNumber', 'panNumber', 'iecNumber', 'vatNumber', 'contactPerson',
      'designation', 'email', 'altEmail', 'mobile', 'officePhone',
      'website', 'addressLine1', 'addressLine2', 'city', 'state',
      'country', 'postalCode', 'billingAddress', 'shippingAddress', 'creditLimit',
      'currency', 'paymentTerms', 'creditPeriod', 'taxCategory', 'customerCategory',
      'accountManager', 'customerNotes', 'updatedAt'
    ],
    Bookings: [
      'bookingRef', 'customerId', 'companyName', 'customerType', 'contactPerson',
      'country', 'phone', 'email', 'bookingDate', 'shipmentType',
      'transportMode', 'origin', 'destination', 'cargoDescription', 'expectedQuantity',
      'cargoWeight', 'cargoVolume', 'preferredShippingDate', 'expectedDeliveryDate', 'bookingStatus',
      'updatedAt'
    ],
    Containers: [
      'containerId', 'containerNumber', 'containerType', 'isoCode', 'containerOwner',
      'shippingLine', 'bookingRef', 'shipmentRef', 'cargoName', 'cargoDescription',
      'cargoCategory', 'hsCode', 'packageType', 'numberOfPackages', 'grossWeight',
      'netWeight', 'volume', 'declaredValue', 'currency', 'dangerousGoods',
      'unNumber', 'hazardClass', 'temperatureReq', 'specialHandling', 'loadingPort',
      'dischargePort', 'stuffingLocation', 'destuffingLocation', 'loadingDate', 'unloadingDate',
      'gateInDate', 'gateOutDate', 'sealNumber', 'vgmWeight', 'inspectionStatus',
      'customsStatus', 'containerStatus', 'currentLocation', 'lastUpdated'
    ],
    Invoices_Payments: [
      'invoiceId', 'invoiceNumber', 'invoiceType', 'shipmentRef', 'bookingRef',
      'customerId', 'customerName', 'billingParty', 'taxId', 'invoiceDate',
      'dueDate', 'currency', 'exchangeRate', 'freightCharge', 'othcCharge',
      'dthcCharge', 'blDocFee', 'customsFee', 'inlandHaulage', 'insuranceBaf',
      'otherCharges', 'discountAmount', 'subtotal', 'taxRate', 'taxAmount',
      'totalAmount', 'paidAmount', 'balanceDue', 'paymentRef', 'paymentDate',
      'paymentMode', 'bankReference', 'paymentStatus', 'remarks', 'updatedAt'
    ],
    Audit_Log: [
      'timestamp', 'action', 'module', 'recordId', 'summary'
    ]
  }
};

/**
 * Ensures all required Google Sheets tabs and header columns exist.
 */
function initializeDatabase() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetNames = Object.keys(DB_CONFIG.HEADERS);
  
  sheetNames.forEach(function(sheetName) {
    let sheet = ss.getSheetByName(sheetName);
    const headers = DB_CONFIG.HEADERS[sheetName];
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      sheet.getRange(1, 1, 1, headers.length)
        .setBackground('#0f172a')
        .setFontColor('#ffffff')
        .setFontWeight('bold');
      sheet.setFrozenRows(1);
    } else if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      sheet.setFrozenRows(1);
    }
  });
  return ss;
}

/**
 * HTTP GET Handler
 * Supports ?action=ping, ?action=getAll, ?action=list&module=Shipments
 */
function doGet(e) {
  try {
    const ss = initializeDatabase();
    const params = (e && e.parameter) ? e.parameter : {};
    const action = params.action || 'getAll';

    if (action === 'ping') {
      return jsonResponse({
        status: 'success',
        app: DB_CONFIG.APP_NAME,
        version: DB_CONFIG.VERSION,
        timestamp: new Date().toISOString(),
        message: 'Google Apps Script ERP Backend is online and connected to Google Sheets.'
      });
    }

    if (action === 'list' && params.sheet) {
      const records = getSheetRecords(ss, params.sheet);
      return jsonResponse({ status: 'success', sheet: params.sheet, data: records });
    }

    // Default: getAll across all operational modules
    const data = {
      shipments: getSheetRecords(ss, DB_CONFIG.SHEETS.SHIPMENTS),
      customers: getSheetRecords(ss, DB_CONFIG.SHEETS.CUSTOMERS),
      bookings: getSheetRecords(ss, DB_CONFIG.SHEETS.BOOKINGS),
      containers: getSheetRecords(ss, DB_CONFIG.SHEETS.CONTAINERS),
      invoices: getSheetRecords(ss, DB_CONFIG.SHEETS.INVOICES)
    };

    return jsonResponse({
      status: 'success',
      timestamp: new Date().toISOString(),
      data: data
    });
  } catch (err) {
    return jsonResponse({ status: 'error', message: err.toString() });
  }
}

/**
 * HTTP POST Handler
 * Uses Content-Type: text/plain;charset=utf-8 to avoid CORS preflight blocks from GitHub Pages.
 * Actions: saveRecord, deleteRecord, syncAll
 */
function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const ss = initializeDatabase();
    const body = (e && e.postData && e.postData.contents) ? JSON.parse(e.postData.contents) : {};
    const action = body.action || '';

    if (action === 'saveRecord') {
      const sheetName = body.sheet;
      const primaryKey = body.primaryKey;
      const record = body.record;
      const result = upsertSheetRecord(ss, sheetName, primaryKey, record);
      appendAuditLog(ss, result.mode.toUpperCase(), sheetName, record[primaryKey], 'Saved via Web App API');
      return jsonResponse({ status: 'success', result: result });
    }

    if (action === 'saveCustomerBooking') {
      const customer = body.customer;
      const booking = body.booking;
      const custRes = upsertSheetRecord(ss, DB_CONFIG.SHEETS.CUSTOMERS, 'customerId', customer);
      const bkgRes = upsertSheetRecord(ss, DB_CONFIG.SHEETS.BOOKINGS, 'bookingRef', booking);
      appendAuditLog(ss, 'UPSERT', 'Customers+Bookings', customer.customerId + ' / ' + booking.bookingRef, 'Customer & Booking saved');
      return jsonResponse({ status: 'success', customerResult: custRes, bookingResult: bkgRes });
    }

    if (action === 'deleteRecord') {
      const sheetName = body.sheet;
      const primaryKey = body.primaryKey;
      const idValue = body.id;
      const deleted = deleteSheetRecord(ss, sheetName, primaryKey, idValue);
      appendAuditLog(ss, 'DELETE', sheetName, idValue, 'Record deleted via Web App API');
      return jsonResponse({ status: 'success', deleted: deleted, id: idValue });
    }

    if (action === 'syncAll') {
      const payload = body.data || {};
      if (Array.isArray(payload.shipments)) replaceSheetRecords(ss, DB_CONFIG.SHEETS.SHIPMENTS, payload.shipments);
      if (Array.isArray(payload.customers)) replaceSheetRecords(ss, DB_CONFIG.SHEETS.CUSTOMERS, payload.customers);
      if (Array.isArray(payload.bookings)) replaceSheetRecords(ss, DB_CONFIG.SHEETS.BOOKINGS, payload.bookings);
      if (Array.isArray(payload.containers)) replaceSheetRecords(ss, DB_CONFIG.SHEETS.CONTAINERS, payload.containers);
      if (Array.isArray(payload.invoices)) replaceSheetRecords(ss, DB_CONFIG.SHEETS.INVOICES, payload.invoices);
      appendAuditLog(ss, 'FULL_SYNC', 'ALL_MODULES', 'BATCH', 'Synchronized all ERP modules from client');
      return jsonResponse({ status: 'success', message: 'All Google Sheets tabs synchronized.' });
    }

    return jsonResponse({ status: 'error', message: 'Unsupported action: ' + action });
  } catch (err) {
    return jsonResponse({ status: 'error', message: err.toString() });
  } finally {
    lock.releaseLock();
  }
}

/**
 * Reads all rows from a sheet and maps them to JSON objects based on header names.
 */
function getSheetRecords(ss, sheetName) {
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() <= 1) return [];
  const values = sheet.getDataRange().getValues();
  const headers = values[0];
  const records = [];
  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    const obj = {};
    for (let c = 0; c < headers.length; c++) {
      obj[headers[c]] = row[c] !== undefined && row[c] !== null ? row[c] : '';
    }
    records.push(obj);
  }
  return records;
}

/**
 * Inserts or updates a record in the target sheet by primaryKey.
 */
function upsertSheetRecord(ss, sheetName, primaryKey, record) {
  const sheet = ss.getSheetByName(sheetName);
  const headers = DB_CONFIG.HEADERS[sheetName];
  if (!sheet || !headers) throw new Error('Invalid sheet name: ' + sheetName);

  const lastRow = sheet.getLastRow();
  const pkIndex = headers.indexOf(primaryKey);
  if (pkIndex === -1) throw new Error('Primary key not found: ' + primaryKey);

  const rowValues = headers.map(function(h) {
    return record[h] !== undefined && record[h] !== null ? String(record[h]) : '';
  });

  if (lastRow > 1) {
    const data = sheet.getRange(2, pkIndex + 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < data.length; i++) {
      if (String(data[i][0]) === String(record[primaryKey])) {
        sheet.getRange(i + 2, 1, 1, headers.length).setValues([rowValues]);
        return { mode: 'updated', row: i + 2, id: record[primaryKey] };
      }
    }
  }

  sheet.appendRow(rowValues);
  return { mode: 'inserted', row: sheet.getLastRow(), id: record[primaryKey] };
}

/**
 * Replaces all rows in a sheet during full batch sync.
 */
function replaceSheetRecords(ss, sheetName, records) {
  const sheet = ss.getSheetByName(sheetName);
  const headers = DB_CONFIG.HEADERS[sheetName];
  if (!sheet || !headers) return;

  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).clearContent();
  }
  if (!records.length) return;

  const matrix = records.map(function(rec) {
    return headers.map(function(h) {
      return rec[h] !== undefined && rec[h] !== null ? String(rec[h]) : '';
    });
  });
  sheet.getRange(2, 1, matrix.length, headers.length).setValues(matrix);
}

/**
 * Deletes a record row by primaryKey value.
 */
function deleteSheetRecord(ss, sheetName, primaryKey, idValue) {
  const sheet = ss.getSheetByName(sheetName);
  const headers = DB_CONFIG.HEADERS[sheetName];
  if (!sheet || sheet.getLastRow() <= 1) return false;
  const pkIndex = headers.indexOf(primaryKey);
  const data = sheet.getRange(2, pkIndex + 1, sheet.getLastRow() - 1, 1).getValues();
  for (let i = data.length - 1; i >= 0; i--) {
    if (String(data[i][0]) === String(idValue)) {
      sheet.deleteRow(i + 2);
      return true;
    }
  }
  return false;
}

/**
 * Appends an audit entry to Audit_Log.
 */
function appendAuditLog(ss, action, moduleName, recordId, summary) {
  const sheet = ss.getSheetByName(DB_CONFIG.SHEETS.AUDIT);
  if (!sheet) return;
  sheet.appendRow([new Date().toISOString(), action, moduleName, String(recordId || ''), summary]);
}

/**
 * Formats JSON output for Google Apps Script Web App.
 */
function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
