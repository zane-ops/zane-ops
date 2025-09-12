import { CheckIcon, XIcon } from "lucide-react";
import { cn } from "~/lib/utils";

interface PasswordRequirement {
  id: string;
  label: string;
  test: (password: string) => number | boolean;
  totalScore?: number;
}

const passwordRequirements: PasswordRequirement[] = [
  {
    id: "length",
    label: "At least 8 characters",
    test: (password) =>
      password.length >= 8 ? true : Math.min(password.length, 6),
    totalScore: 6
  },
  {
    id: "upperkeys",
    label: "Contains at least one uppercase letter",
    test: (password) => /[A-Z]/.test(password)
  },
  {
    id: "lowerkeys",
    label: "Contains at least one lowercase letter",
    test: (password) => /[a-z]/.test(password)
  },
  {
    id: "numbers",
    label: "Contains at least one number",
    test: (password) => /\d/.test(password)
  },
  {
    id: "symbols",
    label: "Contains at least one symbol",
    test: (password) => /[!@#$%^&*(),.?":{}|<>]/.test(password)
  },
  {
    id: "not-common",
    label: "Not a common password",
    test: (password) => {
      if (password.length < 8) return false;
      const commonPasswords = [
        "rootroot",
        "password",
        "mypassword",
        "12345678",
        "123456789",
        "qwertyuiop",
        "abc12345",
        "root1234",
        "password123",
        "admin123",
        "asdfghjkl",
        "zxcvbnm",
        "iloveyou",
        "master123",
        "whatever",
        "zaq12wsx",
        "password1",
        "qwerty123"
      ];
      return !commonPasswords.includes(password.toLowerCase());
    },
    totalScore: 2
  }
];

interface PasswordStrengthIndicatorProps {
  password: string;
  className?: string;
}

export function PasswordStrengthIndicator({
  password,
  className
}: PasswordStrengthIndicatorProps) {
  const requirements = passwordRequirements.map((req) => {
    const met = req.test(password);
    return {
      ...req,
      score: met === true ? (req.totalScore ?? 1) : met === false ? 0 : met,
      total: req.totalScore ?? 1,
      met:
        met === true || (typeof met === "number" && met > (req.totalScore ?? 1))
    };
  });

  const status = requirements.reduce(
    (acc, cur) => {
      acc.total += cur.total;
      acc.completed += cur.score ?? 0;
      return acc;
    },
    { total: 0, completed: 0 }
  );
  const strengthPercentage = (status.completed / status.total) * 100;

  const strengthLabel =
    strengthPercentage >= 90
      ? "Strong"
      : strengthPercentage >= 50
        ? "Medium"
        : strengthPercentage >= 25
          ? "Weak"
          : "Very Weak";

  if (!password) return null;

  return (
    <div
      className={cn(
        "space-y-3 transition animate-in fade-in duration-300",
        className
      )}
    >
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium">Password Strength</span>
          <span
            className={cn(
              "text-sm font-medium",
              strengthPercentage >= 90
                ? "text-green-600"
                : strengthPercentage >= 50
                  ? "text-yellow-600"
                  : "text-red-600"
            )}
          >
            {strengthLabel}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={cn(
              "h-2 rounded-full transition-all duration-300",
              strengthPercentage >= 90
                ? "bg-green-500"
                : strengthPercentage >= 50
                  ? "bg-yellow-500"
                  : strengthPercentage >= 25
                    ? "bg-orange-500"
                    : "bg-red-500"
            )}
            style={{ width: `${strengthPercentage}%` }}
          />
        </div>
      </div>

      <div className="space-y-2">
        <span className="text-sm font-medium">Requirements:</span>
        <ul className="space-y-1">
          {requirements.map((requirement) => (
            <li
              key={requirement.id}
              className="flex items-center gap-2 text-sm"
            >
              <div
                className={cn(
                  "flex items-center justify-center w-4 h-4 rounded-full",
                  requirement.met
                    ? "bg-green-100 text-green-600"
                    : "bg-gray-100 text-gray-400"
                )}
              >
                {requirement.met ? (
                  <CheckIcon size={10} />
                ) : (
                  <XIcon size={10} />
                )}
              </div>
              <span
                className={cn(
                  requirement.met
                    ? "text-green-700 dark:text-green-400"
                    : "text-gray-500 dark:text-gray-400"
                )}
              >
                {requirement.label}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
