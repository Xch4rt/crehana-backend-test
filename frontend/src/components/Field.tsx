// A real <label htmlFor> bound to an <input id>. Never a placeholder standing
// in for a label: a placeholder disappears the moment the user types, is not an
// accessible name, and is not a click target. Every test in this package finds
// its controls by label text for exactly that reason - a field a test can only
// reach by test id is a field a screen reader cannot reach either.

interface FieldProps {
  id: string;
  label: string;
  type?: string;
  value: string;
  required?: boolean;
  autoComplete?: string;
  onChange: (value: string) => void;
}

export default function Field({
  id,
  label,
  type = "text",
  value,
  required = false,
  autoComplete,
  onChange,
}: FieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </div>
  );
}
