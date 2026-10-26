import React, { useState } from "react";
import { api, ApiError } from "../api/client";
import { triggerHaptic } from "../telegram/webapp";

interface ViewingModalProps {
  propertyId: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

const TIME_SLOTS = [
  "10:00 - 12:00",
  "12:00 - 14:00",
  "14:00 - 16:00",
  "16:00 - 18:00",
  "18:00 - 20:00",
];

export const ViewingModal: React.FC<ViewingModalProps> = ({
  propertyId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  // Default to tomorrow
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const defaultDateStr = tomorrow.toISOString().split("T")[0];

  const [date, setDate] = useState<string>(defaultDateStr);
  const [time, setTime] = useState<string>(TIME_SLOTS[0]);
  const [comment, setComment] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!date || !time) {
      setError("Iltimos, sana va vaqtni tanlang");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.createViewingRequest(propertyId, {
        scheduled_date: date,
        preferred_time: time,
        customer_comment: comment.trim() || null,
      });
      triggerHaptic("success");
      onSuccess(res.message);
      onClose();
    } catch (err) {
      triggerHaptic("error");
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Uchrashuv so‘rovini yuborishda xatolik yuz berdi");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">📅 Ko‘rishga yozilish</div>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: "10px",
              backgroundColor: "#fee2e2",
              color: "#b91c1c",
              borderRadius: "8px",
              marginBottom: "12px",
              fontSize: "13px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Sana</label>
            <input
              type="date"
              className="form-input"
              value={date}
              min={defaultDateStr}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Qulay vaqt oralig‘i</label>
            <select
              className="form-select"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              required
            >
              {TIME_SLOTS.map((slot) => (
                <option key={slot} value={slot}>
                  {slot}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Izoh yoki talablar (ixtiyoriy)</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Masalan: oilamiz bilan kelamiz..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          <div className="action-buttons">
            <button type="button" className="secondary-btn" onClick={onClose} disabled={loading}>
              Bekor qilish
            </button>
            <button type="submit" className="primary-btn" disabled={loading}>
              {loading ? "Yuborilmoqda..." : "Yuborish"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
