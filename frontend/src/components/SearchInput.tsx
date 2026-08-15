import type { JSX } from "react";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minLength?: number;
  maxLength?: number;
  disabled?: boolean;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "搜索…",
  minLength = 1,
  maxLength = 128,
  disabled = false,
}: SearchInputProps): JSX.Element {
  const tooShort = value.length > 0 && value.length < minLength;
  return (
    <div className="search-input">
      <input
        type="search"
        className="search-input__field"
        value={value}
        placeholder={placeholder}
        minLength={minLength}
        maxLength={maxLength}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
      {tooShort ? (
        <span className="search-input__hint">至少输入 {minLength} 个字符</span>
      ) : null}
    </div>
  );
}
