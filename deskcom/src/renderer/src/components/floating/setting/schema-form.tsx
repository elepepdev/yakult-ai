import { useState, useEffect, useMemo } from 'react';
import {
  Box, Text, Field, Switch, Select, Input, Textarea, Collapsible, Button, Tag, createListCollection,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useConfigSchema } from '@/context/config-schema-context';
import { useWebSocket } from '@/context/websocket-context';

const fieldLabelStyles = {
  color: 'var(--sk-ink-soft)',
  fontSize: 'sm',
  mb: 1,
  fontWeight: 'medium',
};

const inputStyles = {
  bg: 'var(--sk-paper-raised)',
  border: '1px solid',
  borderColor: 'var(--sk-outline)',
  color: 'var(--sk-ink)',
  _placeholder: { color: 'var(--sk-ink-mute)' },
  _focus: { borderColor: 'var(--sk-pencil-deep)', outline: 'none', boxShadow: '0 0 0 1px var(--sk-pencil-deep)' },
  _hover: { borderColor: 'var(--sk-outline-soft)' },
  rounded: 'md',
  fontSize: 'sm',
};

function LeafField({ node, value, onChange }: { node: any; value: any; onChange: (v: any) => void }) {
  const label = node.description || node.name;

  if (node.type === 'boolean') {
    return (
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
        <Switch.Root checked={!!value} onCheckedChange={(e) => onChange(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>
    );
  }

  if (node.type === 'enum') {
    const options = createListCollection({
      items: (node.options || []).map((o: string) => ({ label: o, value: o })),
    });
    return (
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
        <Select.Root
          collection={options}
          value={value !== undefined && value !== null ? [String(value)] : []}
          onValueChange={(e) => onChange(e.value[0])}
        >
          <Select.Trigger css={inputStyles}>
            <Select.ValueText placeholder="Select..." />
          </Select.Trigger>
          <Select.Content>
            {options.items.map((opt) => (
              <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Field.Root>
    );
  }

  if (node.type === 'number') {
    return (
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
        <Input
          type="number"
          value={value === null || value === undefined ? '' : value}
          onChange={(e) => {
            const n = e.target.value === '' ? null : Number(e.target.value);
            onChange(n);
          }}
          css={inputStyles}
        />
      </Field.Root>
    );
  }

  if (node.multiline || (typeof value === 'string' && value.length > 80)) {
    return (
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
        <Textarea
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          css={inputStyles}
        />
      </Field.Root>
    );
  }

  if (node.secret) {
    return (
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
        <Input
          type="password"
          placeholder={value ? '********' : ''}
          value={value === '********' ? '' : value || ''}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="new-password"
          css={inputStyles}
        />
      </Field.Root>
    );
  }

  if (node.type === 'array') {
    return (
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
        <ArrayEditor value={value || []} onChange={onChange} />
      </Field.Root>
    );
  }

  return (
    <Field.Root>
      <Field.Label css={fieldLabelStyles}>{label}</Field.Label>
      <Input
        value={value === null || value === undefined ? '' : String(value)}
        onChange={(e) => onChange(e.target.value)}
        css={inputStyles}
      />
    </Field.Root>
  );
}

function ArrayEditor({ value, onChange }: { value: any[]; onChange: (v: any[]) => void }) {
  const [items, setItems] = useState<string[]>(value.map((v) => String(v)));
  const [draft, setDraft] = useState('');

  useEffect(() => setItems(value.map((v) => String(v))), [value]);

  const add = () => {
    if (!draft.trim()) return;
    const next = [...items, draft.trim()];
    setItems(next);
    setDraft('');
    onChange(next);
  };

  const remove = (idx: number) => {
    const next = items.filter((_, i) => i !== idx);
    setItems(next);
    onChange(next);
  };

  return (
    <Box spaceY={2}>
      {items.length > 0 && (
        <Box display="flex" flexWrap="wrap" gap={1}>
          {items.map((item, i) => (
            <Tag.Root key={i} size="sm" colorScheme="gray">
              <Tag.Label>{item}</Tag.Label>
              <Tag.CloseTrigger onClick={() => remove(i)} />
            </Tag.Root>
          ))}
        </Box>
      )}
      <Box display="flex" gap={2}>
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
          placeholder="Add item and press Enter"
          css={inputStyles}
        />
        <Button size="sm" onClick={add} colorScheme="blue">Add</Button>
      </Box>
    </Box>
  );
}

const WIDE_SECTION_THRESHOLD = 6;

function ObjectSection({ node, values, onChange }: { node: any; values: Record<string, any>; onChange: (path: string, v: any) => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string>('');

  if (!node.children || node.children.length === 0) {
    return null;
  }

  const isWide = node.children.length > WIDE_SECTION_THRESHOLD;
  const sectionOptions = useMemo(() => createListCollection({
    items: [
      { label: t('settings.showAll'), value: '' },
      ...node.children
        .filter((c: any) => c.type === 'object')
        .map((c: any) => ({ label: c.description || c.name, value: c.name })),
    ],
  }), [node, t]);

  const visibleChildren = isWide && selected
    ? node.children.filter((c: any) => c.name === selected)
    : node.children;

  return (
    <Collapsible.Root open={open} onOpenChange={(e) => setOpen(!!e.open)}>
      <Box borderWidth="var(--sk-border)" borderColor="var(--sk-outline)" rounded="md" bg="var(--sk-paper-raised)" overflow="hidden">
        <Collapsible.Trigger asChild>
          <Box
            as="button"
            width="100%"
            textAlign="left"
            px={3}
            py={2}
            bg="var(--sk-paper-deep)"
            _hover={{ bg: 'var(--sk-outline)' }}
            cursor="pointer"
          >
            <Text fontSize="sm" fontWeight="semibold" color="var(--sk-ink)">
              {node.description || node.name}
              {open ? ' ▾' : ' ▸'}
            </Text>
          </Box>
        </Collapsible.Trigger>
        <Collapsible.Content lazyMount unmountOnExit>
          {isWide && (
            <Box px={3} pt={3}>
              <Select.Root
                collection={sectionOptions}
                value={[selected]}
                onValueChange={(e) => setSelected(e.value[0] ?? '')}
                size="sm"
              >
                <Select.Trigger css={inputStyles}>
                  <Select.ValueText placeholder={t('settings.selectSection')} />
                </Select.Trigger>
                <Select.Content>
                  {sectionOptions.items.map((opt) => (
                    <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </Box>
          )}
          <Box px={3} py={3} spaceY={4}>
            {visibleChildren.map((child: any) => (
              <SchemaField key={child.path} node={child} values={values} onChange={onChange} />
            ))}
          </Box>
        </Collapsible.Content>
      </Box>
    </Collapsible.Root>
  );
}

function SchemaField({ node, values, onChange }: { node: any; values: Record<string, any>; onChange: (path: string, v: any) => void }) {
  if (node.type === 'object') {
    if (!node.children || node.children.length === 0) return null;
    return <ObjectSection node={node} values={values} onChange={onChange} />;
  }
  return <LeafField node={node} value={values[node.path]} onChange={(v) => onChange(node.path, v)} />;
}

interface SchemaFormProps {
  rootPath: string;
  /** Restrict which direct children of the root node are rendered. */
  only?: string[];
}

export default function SchemaForm({ rootPath, only }: SchemaFormProps) {
  const { t } = useTranslation();
  const { schema, refreshSchema, onSchemaRefreshed } = useConfigSchema();
  const { sendMessage } = useWebSocket();
  const [values, setValues] = useState<Record<string, any>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  const rootNode = useMemo(() => {
    if (!schema) return null;
    const find = (node: any): any => {
      if (node.path === rootPath) return node;
      for (const child of node.children || []) {
        if (child.type === 'object') {
          const r = find(child);
          if (r) return r;
        }
      }
      return null;
    };
    return find(schema);
  }, [schema, rootPath]);

  // Collect leaf values under rootNode
  const collectValues = (node: any, out: Record<string, any> = {}): Record<string, any> => {
    for (const child of node.children || []) {
      if (only && !only.includes(child.name)) continue;
      if (child.type === 'object') {
        collectValues(child, out);
      } else if (child.value !== undefined) {
        out[child.path] = child.value;
      }
    }
    return out;
  };

  useEffect(() => {
    if (rootNode) {
      setValues(collectValues(rootNode));
      setDirty({});
    }
  }, [rootNode]);

  useEffect(() => onSchemaRefreshed(() => {
    if (rootNode) {
      setValues(collectValues(rootNode));
      setDirty({});
    }
  }), [rootNode, onSchemaRefreshed]);

  if (!rootNode) {
    return (
      <Box p={4} bg="var(--sk-paper-raised)" rounded="md" borderWidth="var(--sk-border)" borderColor="var(--sk-outline)">
        <Text color="var(--sk-ink-faint)" fontSize="sm">{t('settings.schemaLoading')}</Text>
      </Box>
    );
  }

  const handleChange = (path: string, v: any) => {
    setValues((prev) => ({ ...prev, [path]: v }));
    setDirty((prev) => ({ ...prev, [path]: true }));
  };

  const hasDirty = Object.values(dirty).some(Boolean);

  const save = () => {
    const updates: Record<string, any> = {};
    for (const [path, isDirty] of Object.entries(dirty)) {
      if (isDirty) {
        updates[path] = values[path];
      }
    }
    if (Object.keys(updates).length === 0) return;
    setSaving(true);
    sendMessage({ type: 'save-config-fields', updates, lang: 'en' });
    // refresh schema shortly after save to reflect server state
    setTimeout(() => {
      refreshSchema();
      setSaving(false);
    }, 1500);
  };

  const reset = () => {
    if (rootNode) {
      setValues(collectValues(rootNode));
      setDirty({});
    }
  };

  return (
    <Box spaceY={4}>
      <Box spaceY={4}>
        {rootNode.children
          .filter((child: any) => !only || only.includes(child.name))
          .map((child: any) => (
            <SchemaField key={child.path} node={child} values={values} onChange={handleChange} />
          ))}
      </Box>

      <Box display="flex" gap={2} pt={2}>
        <Button
          size="sm"
          colorScheme="blue"
          onClick={save}
          disabled={!hasDirty || saving}
          isLoading={saving}
        >
          {t('settings.save')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={reset}
          disabled={!hasDirty}
          bg="var(--sk-paper-raised)"
          color="var(--sk-ink-soft)"
          border="1px solid"
          borderColor="var(--sk-outline)"
          _hover={{ bg: 'var(--sk-outline)', color: 'var(--sk-ink)' }}
        >
          {t('settings.reset')}
        </Button>
      </Box>
    </Box>
  );
}
