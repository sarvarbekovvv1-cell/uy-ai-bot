import { describe, expect, it } from "vitest";

describe("Admin Settings Validations", () => {
  const validateUsername = (val: string): { valid: boolean; error?: string } => {
    const trimmed = val.trim();
    if (!trimmed) return { valid: false, error: "Yangi foydalanuvchi nomini kiriting." };
    if (trimmed.length < 3) return { valid: false, error: "Foydalanuvchi nomi kamida 3 ta belgidan iborat bo'lishi kerak." };
    if (trimmed.length > 50) return { valid: false, error: "Foydalanuvchi nomi 50 ta belgidan oshmasligi kerak." };
    if (!/^[a-zA-Z0-9_.-]+$/.test(trimmed)) {
      return { valid: false, error: "Foydalanuvchi nomida faqat lotin harflari, raqamlar, chiziqcha va nuqta ruxsat etilgan." };
    }
    return { valid: true };
  };

  const validatePassword = (
    current: string,
    newPass: string,
    confirmPass: string
  ): { valid: boolean; error?: string } => {
    if (!current) return { valid: false, error: "Joriy parolni kiriting." };
    if (!newPass) return { valid: false, error: "Yangi parolni kiriting." };
    if (newPass.length < 8) return { valid: false, error: "Yangi parol kamida 8 ta belgidan iborat bo'lishi kerak." };
    if (newPass.length > 128) return { valid: false, error: "Yangi parol 128 ta belgidan oshmasligi kerak." };
    if (newPass !== confirmPass) return { valid: false, error: "Yangi parollar bir-biriga mos kelmadi." };
    return { valid: true };
  };

  const validateBrokerPhone = (val: string): { valid: boolean; error?: string } => {
    const trimmed = val.trim();
    if (!trimmed) return { valid: false, error: "Telefon raqamini kiriting." };
    const digitsOnly = trimmed.replace(/\D/g, "");
    if (digitsOnly.length < 9 || digitsOnly.length > 15) {
      return {
        valid: false,
        error: "Telefon raqami noto'g'ri formatda. Kamida 9 ta raqam bo'lishi kerak (masalan: +998 90 123 45 67).",
      };
    }
    return { valid: true };
  };

  it("validates username format and length", () => {
    expect(validateUsername("").valid).toBe(false);
    expect(validateUsername("  ").valid).toBe(false);
    expect(validateUsername("ab").valid).toBe(false); // too short
    expect(validateUsername("a".repeat(51)).valid).toBe(false); // too long
    expect(validateUsername("admin@evil").valid).toBe(false); // invalid char '@'
    expect(validateUsername("admin space").valid).toBe(false); // space not allowed
    expect(validateUsername("admin_user-1").valid).toBe(true);
    expect(validateUsername("superadmin.boss").valid).toBe(true);
  });

  it("validates password length and confirmation match", () => {
    expect(validatePassword("", "NewPassword123!", "NewPassword123!").valid).toBe(false);
    expect(validatePassword("OldPassword123!", "short", "short").valid).toBe(false);
    expect(validatePassword("OldPassword123!", "a".repeat(129), "a".repeat(129)).valid).toBe(false);
    expect(validatePassword("OldPassword123!", "NewPassword123!", "DifferentPassword123!").valid).toBe(false);
    expect(validatePassword("OldPassword123!", "NewPassword123!", "NewPassword123!").valid).toBe(true);
  });

  it("validates broker phone format and length", () => {
    expect(validateBrokerPhone("").valid).toBe(false);
    expect(validateBrokerPhone("   ").valid).toBe(false);
    expect(validateBrokerPhone("123").valid).toBe(false); // too short
    expect(validateBrokerPhone("+998 71 200 00 00").valid).toBe(true);
    expect(validateBrokerPhone("+998 90 123 45 67").valid).toBe(true);
    expect(validateBrokerPhone("901234567").valid).toBe(true);
    expect(validateBrokerPhone("1".repeat(16)).valid).toBe(false); // too long
  });
});
