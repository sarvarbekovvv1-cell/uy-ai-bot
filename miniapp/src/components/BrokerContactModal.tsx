import React, { useState } from "react";
import { api, ApiError } from "../api/client";
import { triggerHaptic } from "../telegram/webapp";

interface BrokerContactModalProps {
  propertyId: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

export const BrokerContactModal: React.FC<BrokerContactModalProps> = ({
  propertyId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [comment, setComment] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.createBrokerContact(propertyId, {
        comment: comment.trim() || null,
      });
      triggerHaptic("success");
      onSuccess(res.message);
      onClose();
    } catch (err) {
      triggerHaptic("error");
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Broker bilan bog‘lanish so‘rovida xatolik yuz berdi");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">👨‍💼 Broker bilan bog‘lanish</div>
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
          <p style={{ fontSize: "13px", color: "var(--hint-color)", marginBottom: "14px" }}>
            Brokerimiz siz bilan tez orada Telegram yoki telefon orqali bog‘lanib, barcha
            savollaringizga batafsil javob beradi.
          </p>

          <div className="form-group">
            <label className="form-label">Savol yoki qo‘shimcha ma’lumot (ixtiyoriy)</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Masalan: ipoteka orqali olsa bo‘ladimi?..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          <div className="action-buttons">
            <button type="button" className="secondary-btn" onClick={onClose} disabled={loading}>
              Bekor qilish
            </button>
            <button type="submit" className="primary-btn" disabled={loading}>
              {loading ? "Yuborilmoqda..." : "Bog‘lanish"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
