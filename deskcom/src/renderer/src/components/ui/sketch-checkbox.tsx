import { Checkbox, type CheckboxCheckedChangeDetails } from '@chakra-ui/react';

interface SketchCheckboxProps {
  checked: boolean;
  onCheckedChange: (e: CheckboxCheckedChangeDetails) => void;
  colorPalette?: string;
}

/**
 * Hand-drawn checkbox: squiggly ink border, rough corner radius, marker-colored check.
 */
export function SketchCheckbox({ checked, onCheckedChange, colorPalette = 'green' }: SketchCheckboxProps) {
  return (
    <Checkbox.Root
      checked={checked}
      onCheckedChange={onCheckedChange}
      colorPalette={colorPalette}
      css={{
        '& [data-part="control"]': {
          border: '1.5px solid var(--sk-outline-hover)',
          borderRadius: '6px 4px 7px 3px',
          bg: checked ? 'var(--sk-pencil)' : 'transparent',
          transition: 'all 0.15s ease',
        },
      }}
    >
      <Checkbox.HiddenInput />
      <Checkbox.Control borderColor="var(--sk-outline-hover)" />
    </Checkbox.Root>
  );
}
