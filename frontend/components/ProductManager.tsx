"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface Product {
  product_id: string;
  sku: string;
  asin: string;
  title: string;
  price: string;
  active: boolean;
  category: string;
  keywords: string;
  research_keywords: string;
  target_acos?: number;
}

interface ProductFormState {
  product_id: string;
  sku: string;
  asin: string;
  title: string;
  selling_price: string;
  active: boolean;
  category: string;
  keywords: string;
  research_keywords: string;
  target_acos: string;
}

const EMPTY_FORM: ProductFormState = {
  product_id: "",
  sku: "",
  asin: "",
  title: "",
  selling_price: "",
  active: true,
  category: "",
  keywords: "",
  research_keywords: "",
  target_acos: "",
};

function productToForm(p: Product): ProductFormState {
  return {
    product_id: p.product_id,
    sku: p.sku,
    asin: p.asin,
    title: p.title,
    selling_price: p.price ?? "",
    active: p.active,
    category: p.category,
    keywords: p.keywords,
    research_keywords: p.research_keywords,
    target_acos: p.target_acos != null ? String(p.target_acos) : "",
  };
}

export default function ProductManager() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/products");
      const data = await response.json();
      setProducts(data.products || []);
      setError("");
    } catch (err) {
      setError("Failed to load products");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const startAdd = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setNotice("");
    setError("");
  };

  const startEdit = (p: Product) => {
    setEditingId(p.product_id);
    setForm(productToForm(p));
    setShowForm(true);
    setNotice("");
    setError("");
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const buildPayload = () => ({
    product_id: form.product_id.trim(),
    sku: form.sku.trim(),
    asin: form.asin.trim(),
    title: form.title.trim(),
    selling_price: form.selling_price === "" ? null : parseFloat(form.selling_price),
    active: form.active,
    category: form.category.trim(),
    keywords: form.keywords.trim(),
    research_keywords: form.research_keywords.trim(),
    target_acos: form.target_acos === "" ? null : parseFloat(form.target_acos),
  });

  const handleSubmit = async () => {
    if (!form.product_id.trim() || !form.sku.trim()) {
      setError("Product ID and SKU are required");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const payload = buildPayload();
      const isEdit = editingId !== null;
      const url = isEdit ? `/api/products/${encodeURIComponent(editingId!)}` : "/api/products";
      const method = isEdit ? "PUT" : "POST";

      // Updates only need fields that actually change - but sending the
      // full form is harmless and simpler than diffing, since the backend
      // treats every field in the payload as "set this", not "only these
      // fields exist".
      const body = isEdit
        ? { ...payload, product_id: undefined }
        : payload;

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();

      if (!response.ok) {
        setError(data.error || `Failed to ${isEdit ? "update" : "create"} product`);
        return;
      }

      setNotice(isEdit ? `Updated ${editingId}` : `Added ${payload.product_id}`);
      cancelForm();
      fetchProducts();
    } catch (err) {
      setError(`Failed to ${editingId ? "update" : "create"} product`);
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 flex items-start justify-between">
          <div>
            <Link href="/" className="text-emerald-400 hover:text-emerald-300 mb-4 inline-block">
              ← Back to Dashboard
            </Link>
            <h1 className="text-4xl font-bold text-white mb-2">Products</h1>
            <p className="text-gray-300">Manage the product feed used to build campaigns</p>
          </div>
          <button
            onClick={startAdd}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded transition h-fit"
          >
            + Add Product
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-300">
            {error}
          </div>
        )}
        {notice && (
          <div className="mb-6 p-4 bg-emerald-900/30 border border-emerald-700 rounded-lg text-emerald-300">
            {notice}
          </div>
        )}

        {showForm && (
          <div className="mb-8 bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg p-6">
            <h2 className="text-xl font-bold text-white mb-4">
              {editingId ? `Edit ${editingId}` : "Add Product"}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Product ID" required disabled={editingId !== null}>
                <input
                  value={form.product_id}
                  disabled={editingId !== null}
                  onChange={(e) => setForm({ ...form, product_id: e.target.value })}
                  placeholder="NWS_029"
                  className={inputClass}
                />
              </Field>
              <Field label="SKU" required>
                <input
                  value={form.sku}
                  onChange={(e) => setForm({ ...form, sku: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Title">
                <input
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="ASIN">
                <input
                  value={form.asin}
                  onChange={(e) => setForm({ ...form, asin: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Selling Price ($)">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.selling_price}
                  onChange={(e) => setForm({ ...form, selling_price: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Category">
                <input
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Target ACOS (e.g. 0.25 = 25%)">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={form.target_acos}
                  onChange={(e) => setForm({ ...form, target_acos: e.target.value })}
                  placeholder="Leave blank to use the account default"
                  className={inputClass}
                />
              </Field>
              <Field label="Active">
                <div className="flex items-center h-10">
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(e) => setForm({ ...form, active: e.target.checked })}
                    className="w-4 h-4 accent-emerald-500"
                  />
                  <span className="ml-2 text-sm text-gray-300">
                    Eligible for campaign creation
                  </span>
                </div>
              </Field>
              <Field label="Keywords (comma-separated)" wide>
                <input
                  value={form.keywords}
                  onChange={(e) => setForm({ ...form, keywords: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Research Keywords (comma-separated)" wide>
                <input
                  value={form.research_keywords}
                  onChange={(e) => setForm({ ...form, research_keywords: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleSubmit}
                disabled={saving}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-600 text-white font-medium rounded transition"
              >
                {saving ? "Saving..." : editingId ? "Save Changes" : "Add Product"}
              </button>
              <button
                onClick={cancelForm}
                disabled={saving}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white font-medium rounded transition"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg overflow-hidden">
          {loading ? (
            <p className="text-gray-400 p-6">Loading products...</p>
          ) : products.length === 0 ? (
            <p className="text-gray-400 p-6">No products yet — add one to get started.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-800/60 text-gray-400 text-left">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">SKU</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Target ACOS</th>
                  <th className="px-4 py-3">Active</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-600/30">
                {products.map((p) => (
                  <tr key={p.product_id} className="text-gray-200 hover:bg-slate-600/20">
                    <td className="px-4 py-3 max-w-xs truncate" title={p.title}>
                      {p.title || <span className="text-gray-500 italic">Untitled</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-400">{p.sku}</td>
                    <td className="px-4 py-3">{p.price ? `$${p.price}` : "—"}</td>
                    <td className="px-4 py-3 text-gray-400">{p.category || "—"}</td>
                    <td className="px-4 py-3 text-gray-400">
                      {p.target_acos != null ? `${(p.target_acos * 100).toFixed(0)}%` : "default"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          p.active
                            ? "bg-emerald-900/50 text-emerald-300"
                            : "bg-slate-600/50 text-gray-400"
                        }`}
                      >
                        {p.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => startEdit(p)}
                        className="text-emerald-400 hover:text-emerald-300 text-xs font-medium"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

const inputClass =
  "w-full px-4 py-2 bg-slate-600/30 border border-slate-600/50 rounded text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500";

function Field({
  label,
  required,
  disabled,
  wide,
  children,
}: {
  label: string;
  required?: boolean;
  disabled?: boolean;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={wide ? "md:col-span-2" : ""}>
      <label className={`block text-sm font-medium mb-2 ${disabled ? "text-gray-500" : "text-gray-300"}`}>
        {label}
        {required && <span className="text-red-400 ml-1">*</span>}
      </label>
      {children}
    </div>
  );
}
