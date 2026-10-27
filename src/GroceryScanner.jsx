import { useEffect, useState } from 'react';
import { ArrowRight, Check, CloudUpload, FileText, LoaderCircle, RotateCcw } from 'lucide-react';
import {
  addReceiptItem, confirmReceipt, getReceipt, getReceiptCategories, getReceipts,
  getSavedProfileId, removeReceiptItem, retryReceipt, scanReceipt,
  updateReceipt, updateReceiptItem,
} from './services/api.js';

const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const units = ['kg', 'g', 'l', 'ml', 'each', 'dozen', 'packet', 'pack', 'pouch', 'bottle', 'box', 'tin', 'bag', 'bunch'];
const moneyFields = ['subtotal', 'discount_total', 'tax_total', 'total_amount'];

export default function GroceryScanner() {
  const profileId = getSavedProfileId();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [header, setHeader] = useState({});
  const [categories, setCategories] = useState([]);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getReceiptCategories().then(setCategories).catch(e => setError(e.message));
    if (profileId) getReceipts(profileId).then(setHistory).catch(e => setError(e.message));
  }, []);

  function hydrate(r) {
    setReceipt(r);
    setDrafts(Object.fromEntries(r.items.map(item => [item.id, {
      product_name: item.product_name ?? '', quantity: item.quantity ?? '', unit: item.unit ?? '',
      package_size: item.package_size ?? '', package_size_unit: item.package_size_unit ?? '',
      mrp: item.mrp ?? '', price_column_value: item.price_column_value ?? '',
      price_column_semantics: item.price_column_semantics ?? 'UNKNOWN',
      unit_price: item.unit_price ?? '', line_total: item.line_total ?? '', food_category: item.food_category ?? '',
    }])));
    setHeader({
      merchant_name: r.merchant_name ?? '', store_address: r.store_address ?? '', receipt_date: r.receipt_date ?? '',
      invoice_number: r.invoice_number ?? '', gstin: r.gstin ?? '', currency: r.currency ?? '', subtotal: r.subtotal ?? '',
      discount_total: r.discount_total ?? '', tax_total: r.tax_total ?? '', total_amount: r.total_amount ?? '',
    });
  }

  async function refreshHistory() {
    if (profileId) setHistory(await getReceipts(profileId));
  }

  function choose(nextFile) {
    if (!nextFile) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(nextFile.type)) {
      setError('Choose a JPG, PNG, or WebP image.'); return;
    }
    if (nextFile.size > 10 * 1024 * 1024) { setError('Receipt images must be 10 MB or smaller.'); return; }
    if (preview.startsWith('blob:')) URL.revokeObjectURL(preview);
    setFile(nextFile); setReceipt(null); setPreview(URL.createObjectURL(nextFile)); setError('');
  }

  async function scan() {
    if (!file || !profileId) return;
    setBusy(true); setError('');
    try { hydrate(await scanReceipt(profileId, file)); await refreshHistory(); }
    catch (e) { setError(e.message); await refreshHistory().catch(() => {}); }
    finally { setBusy(false); }
  }

  function setItemField(id, field, value) {
    setDrafts(current => ({ ...current, [id]: { ...current[id], [field]: value } }));
  }

  async function saveHeader() {
    try {
      const changes = Object.fromEntries(Object.entries(header).map(([key, value]) => [
        key, moneyFields.includes(key) ? (value === '' ? null : value) : (value || null),
      ]));
      hydrate(await updateReceipt(receipt.id, profileId, changes));
    } catch (e) { setError(e.message); }
  }

  async function saveItem(item) {
    const draft = drafts[item.id] ?? {};
      const numeric = key => draft[key] === '' ? null : draft[key];
    try {
      hydrate(await updateReceiptItem(receipt.id, item.id, profileId, {
        product_name: draft.product_name, quantity: numeric('quantity'), unit: draft.unit || null,
        package_size: numeric('package_size'), package_size_unit: draft.package_size_unit || null,
        mrp: numeric('mrp'), price_column_value: numeric('price_column_value'),
        price_column_semantics: draft.price_column_semantics || 'UNKNOWN',
        unit_price: numeric('unit_price'), line_total: numeric('line_total'),
        ...(draft.food_category !== item.food_category ? { food_category: draft.food_category || null } : {}),
      }));
    } catch (e) { setError(e.message); }
  }

  async function addMissingItem() {
    try { hydrate(await addReceiptItem(receipt.id, profileId, { product_name: 'New grocery item' })); }
    catch (e) { setError(e.message); }
  }

  async function removeItem(item) {
    try { hydrate(await removeReceiptItem(receipt.id, item.id, profileId)); }
    catch (e) { setError(e.message); }
  }

  async function confirm() {
    setBusy(true); setError('');
    try { hydrate(await confirmReceipt(receipt.id, profileId)); await refreshHistory(); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function retry() {
    setBusy(true); setError('');
    try { hydrate(await retryReceipt(receipt.id, profileId)); await refreshHistory(); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function openHistory(id) {
    setBusy(true);
    try {
      hydrate(await getReceipt(id, profileId));
      setPreview(`${apiBase}/api/receipts/${id}/image?profile_id=${profileId}`);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  const confirmed = receipt?.ocr_status === 'CONFIRMED';
  return <>
    <div className="page-title"><div>
      <div className="eyebrow">GROCERY RECEIPT · REVIEW BEFORE SAVING</div>
      <h1>Grocery Scanner</h1>
      <p>Read a receipt locally, correct detected details, and save confirmed grocery records.</p>
    </div></div>

    {!profileId ? <div className="card activity-empty"><b>Create a profile before scanning.</b><a className="button" href="/onboarding">Create profile <ArrowRight size={14}/></a></div> : <>
      {error && <div className="save-error" role="alert">{error}<button onClick={() => setError('')}>Dismiss</button></div>}

      {!receipt && <div className="upload-layout"><section className="card upload-card">
        <div className="upload-kicker"><span className="upload-kicker-icon"><FileText size={17}/></span><div>
          <b>Receipt images stay on this server</b><span>OCR runs locally. You can review every detected row against the original photo.</span>
        </div></div>
        <label className="dropzone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); choose(e.dataTransfer.files?.[0]); }}>
          <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={e => choose(e.target.files?.[0])}/>
          <CloudUpload size={26}/><b>{file?.name || 'Choose or drop a grocery receipt photo'}</b><span>JPG, PNG or WebP · maximum 10 MB</span>
        </label>
        {preview && <><img src={preview} alt="Receipt preview" className="receipt-upload-preview"/><button type="button" className="quiet-button" onClick={() => { if (preview.startsWith('blob:')) URL.revokeObjectURL(preview); setFile(null); setPreview(''); }}>Remove photo</button></>}
        <button className="button upload-continue" disabled={!file || busy} onClick={scan}>
          {busy ? <><LoaderCircle size={15}/> Uploading and reading receipt locally…</> : <>Scan receipt <ArrowRight size={15}/></>}
        </button>
        <p className="upload-footnote">OCR extracts receipt data only. Carbon estimates require a confirmed supported quantity and approved factor.</p>
      </section><aside className="upload-side"><span className="eyebrow">HOW IT WORKS</span><h3>OCR first, review before saving.</h3><p>Prices never become quantities. Pack counts and package size stay separate unless the receipt states both.</p></aside></div>}

      {receipt && <>
        <div className="card receipt-summary"><div><div className="eyebrow">{receipt.ocr_engine} · {receipt.ocr_status}</div>
          <h2>{confirmed ? 'Confirmed receipt' : 'Review detected items'}</h2>
          <p>OCR confidence describes text recognition only. Receipt confirmation does not establish the scientific accuracy of a future carbon estimate.</p>
        </div><div className="receipt-total">{receipt.total_amount != null ? `${receipt.currency || 'Currency not detected'} ${receipt.total_amount.toFixed(2)}` : 'Total not detected'}</div></div>

        {receipt.ocr_status === 'FAILED' && <div className="card activity-empty" role="alert"><b>Receipt reading failed.</b><span>{receipt.processing_error || 'Local OCR could not process this image.'}</span><button className="button" disabled={busy} onClick={retry}>Retry local OCR</button></div>}
        {receipt.ocr_status === 'REVIEW_REQUIRED' && !receipt.items.some(item => item.user_corrected) && <button className="quiet-button" disabled={busy} onClick={retry}>Re-run extraction with current model</button>}
        {receipt.warnings?.map((warning, index) => <div className="save-error" role="status" key={index}>{warning}</div>)}
        {preview && <div className="card receipt-preview"><img src={preview} alt="Uploaded grocery receipt for comparison"/></div>}

        {receipt.ocr_status !== 'FAILED' && <>
          <section className="card receipt-fields receipt-header-fields" aria-label="Receipt details">
            <label>Store name<input value={header.merchant_name ?? ''} onChange={e => setHeader(h => ({ ...h, merchant_name: e.target.value }))}/></label>
            <label>Store address<input value={header.store_address ?? ''} onChange={e => setHeader(h => ({ ...h, store_address: e.target.value }))}/></label>
            <label>Purchase date<input type="date" value={header.receipt_date ?? ''} onChange={e => setHeader(h => ({ ...h, receipt_date: e.target.value }))}/></label>
            <label>Invoice number<input value={header.invoice_number ?? ''} onChange={e => setHeader(h => ({ ...h, invoice_number: e.target.value }))}/></label>
            <label>GSTIN<input value={header.gstin ?? ''} onChange={e => setHeader(h => ({ ...h, gstin: e.target.value }))}/></label>
            <label>Currency<input value={header.currency ?? ''} placeholder="INR" onChange={e => setHeader(h => ({ ...h, currency: e.target.value.toUpperCase() }))}/></label>
            {moneyFields.map(field => <label key={field}>{({ subtotal: 'Subtotal', discount_total: 'Discount total', tax_total: 'Tax total', total_amount: 'Final payable total' })[field]} ({receipt.currency || 'currency not detected'})
              <input type="number" min="0" step="0.01" value={header[field] ?? ''} onChange={e => setHeader(h => ({ ...h, [field]: e.target.value }))}/>
            </label>)}
            <button className="quiet-button" disabled={busy || confirmed} onClick={saveHeader}>Save receipt details</button>
          </section>

          <div className="receipt-items">{receipt.items.map((item, index) => {
            const draft = drafts[item.id] ?? {};
            return <article className="card receipt-item" key={item.id}>
              <div className="receipt-item-head"><b>Line {index + 1}</b><span className={`receipt-state ${item.needs_confirmation ? 'NEEDS_REVIEW' : item.emissions_status}`}>{item.needs_confirmation ? 'needs product review' : item.emissions_status.replaceAll('_', ' ')}</span></div>
              <small className="receipt-raw">Receipt text: {item.raw_text || 'Manually added — enter the printed description.'} · OCR confidence {item.ocr_confidence == null ? 'not available' : `${Math.round(item.ocr_confidence * 100)}%`}</small>
              {item.total_content_quantity != null && <small className="receipt-raw">Total contents: {item.total_content_quantity} {item.total_content_unit} across {item.quantity} {item.unit}{Number(item.quantity) === 1 ? '' : 's'} ({item.package_size} {item.package_size_unit} each).</small>}
              <small className="receipt-raw">{item.match_method ? `Product match: ${item.match_method.replaceAll('_', ' ').toLowerCase()} · ${item.match_confidence == null ? 'confidence unavailable' : `${Math.round(item.match_confidence * 100)}%`}` : 'No automatic product match; select a category only when supported.'}</small>
              <div className="receipt-fields">
                <label>Product description<input aria-label={`Product description line ${index + 1}`} value={draft.product_name ?? ''} onChange={e => setItemField(item.id, 'product_name', e.target.value)}/></label>
                <label>MRP (₹)<input type="number" min="0" step="0.01" value={draft.mrp ?? ''} onChange={e => setItemField(item.id, 'mrp', e.target.value)}/></label>
                <label>Quantity<input aria-label={`Quantity line ${index + 1}`} type="number" min="0" step="0.001" value={draft.quantity ?? ''} onChange={e => setItemField(item.id, 'quantity', e.target.value)}/></label>
                <label>Quantity unit<select aria-label={`Quantity unit line ${index + 1}`} value={draft.unit ?? ''} onChange={e => setItemField(item.id, 'unit', e.target.value)}><option value="">Unknown</option>{units.map(unit => <option key={unit}>{unit}</option>)}</select></label>
                <label>Package size<input type="number" min="0" step="0.001" value={draft.package_size ?? ''} onChange={e => setItemField(item.id, 'package_size', e.target.value)}/></label>
                <label>Package size unit<select value={draft.package_size_unit ?? ''} onChange={e => setItemField(item.id, 'package_size_unit', e.target.value)}><option value="">Unknown</option>{['kg', 'g', 'l', 'ml'].map(unit => <option key={unit}>{unit}</option>)}</select></label>
                <label>Price shown on receipt (₹)<input type="number" min="0" step="0.01" value={draft.price_column_value ?? ''} onChange={e => setItemField(item.id, 'price_column_value', e.target.value)}/></label>
                <label>Price interpretation<select value={draft.price_column_semantics ?? 'UNKNOWN'} onChange={e => setItemField(item.id, 'price_column_semantics', e.target.value)}><option value="UNKNOWN">Unclear — review</option><option value="USER_CONFIRMED_UNIT_PRICE">Unit price / rate (confirmed)</option><option value="USER_CONFIRMED_LINE_AMOUNT">Line amount (confirmed)</option></select></label>
                <label>Unit price<input type="number" min="0" step="0.01" value={draft.unit_price ?? ''} onChange={e => setItemField(item.id, 'unit_price', e.target.value)}/></label>
                <label>Line total<input type="number" min="0" step="0.01" value={draft.line_total ?? ''} onChange={e => setItemField(item.id, 'line_total', e.target.value)}/></label>
                <label>Food category<select value={draft.food_category ?? ''} onChange={e => setItemField(item.id, 'food_category', e.target.value)}><option value="">Unmatched / not confirmed</option>{categories.map(category => <option key={category.key} value={category.key}>{category.label} · approved factor available</option>)}</select></label>
              </div>
              {item.quantity_unit_inferred && <small className="save-error" role="status">Quantity unit {item.unit} was inferred from the product and receipt context. Confirm or change it before saving.</small>}
              {item.suggested_category && <small className="receipt-raw">Suggested category: {item.suggested_category.replaceAll('.', ' / ')} · confirm product identity and category.</small>}
              {item.warnings?.map((warning, warningIndex) => <small className="save-error" role="status" key={warningIndex}>{warning}</small>)}
              <button className="quiet-button" disabled={busy || confirmed} onClick={() => saveItem(item)}>Save row correction</button>
              {!confirmed && <button className="quiet-button" onClick={() => removeItem(item)}>Remove line</button>}
              {item.emissions_kg_co2e != null && <div className="receipt-result"><b>{item.emissions_kg_co2e.toFixed(4)} kgCO₂e estimate</b><small>{item.calculation_details?.factor_source}: global category-average proxy; not India-specific.</small></div>}
              {item.emissions_status === 'FACTOR_UNAVAILABLE' && <div className="receipt-result">No approved emission factor is available for this category.</div>}
              {item.emissions_status === 'QUANTITY_UNAVAILABLE' && <div className="receipt-result">No supported mass quantity is available for an estimate.</div>}
            </article>;
          })}</div>
          {!confirmed && <button className="quiet-button" disabled={busy} onClick={addMissingItem}>Add a missing line item</button>}
          <details className="card raw-ocr"><summary>Show complete raw OCR text</summary><pre>{receipt.raw_ocr_text || 'No text recognized.'}</pre></details>
          <div className="receipt-confirm"><span>{receipt.items.length} receipt items · factor coverage is separate from OCR and product matching.</span>
            <button className="button" disabled={busy || !receipt.items.length || confirmed} onClick={confirm}>{busy ? 'Saving…' : confirmed ? 'Receipt confirmed' : 'Confirm and Save Receipt'} <Check size={15}/></button>
          </div>
        </>}
        <button className="quiet-button" onClick={() => { setReceipt(null); setPreview(''); setFile(null); }}><RotateCcw size={13}/> Scan another receipt</button>
      </>}

      {history.length > 0 && <section className="receipt-history"><h2>Receipt history</h2>{history.map(r => <button className="card receipt-history-row" key={r.id} onClick={() => openHistory(r.id)}>
        <span><b>{r.merchant_name || 'Grocery receipt'}</b><small>{new Date(r.created_at).toLocaleDateString()} · {r.summary.total_items} items · {r.ocr_status}</small></span><strong>Open receipt</strong>
      </button>)}</section>}
    </>}
  </>;
}
