import type { CharacterCard, Worldbook } from './types';

export type SeedImportIssueSeverity = 'error' | 'warning';
export type SeedImportIssueScope = 'worldbook' | 'characters' | 'import';

export interface SeedImportIssue {
  id: string;
  severity: SeedImportIssueSeverity;
  scope: SeedImportIssueScope;
  path: string;
  message: string;
  line?: number;
  column?: number;
}

export interface SeedImportPreflight {
  worldbook: Worldbook | null;
  characters: CharacterCard[];
  issues: SeedImportIssue[];
  errorCount: number;
  warningCount: number;
  canImport: boolean;
  summary: {
    worldbookId: string;
    worldbookTitle: string;
    locationCount: number;
    eventSeedCount: number;
    characterCount: number;
  };
}

interface ValidateImportDraftsArgs {
  worldbookDraft: string;
  characterDraft: string;
  existingWorldbookIds: string[];
  existingCharacterIds: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toLineColumn(raw: string, position: number) {
  const before = raw.slice(0, Math.max(0, position));
  const segments = before.split('\n');
  return {
    line: segments.length,
    column: segments[segments.length - 1].length + 1,
  };
}

function parseJsonLocation(raw: string, error: unknown) {
  if (!(error instanceof Error)) return {};
  const match = error.message.match(/position (\d+)/i);
  if (!match) return {};
  return toLineColumn(raw, Number(match[1]));
}

function pushIssue(
  issues: SeedImportIssue[],
  severity: SeedImportIssueSeverity,
  scope: SeedImportIssueScope,
  path: string,
  message: string,
  location?: { line?: number; column?: number },
) {
  issues.push({
    id: `${scope}-${issues.length + 1}`,
    severity,
    scope,
    path,
    message,
    line: location?.line,
    column: location?.column,
  });
}

function readString(
  record: Record<string, unknown>,
  key: string,
  issues: SeedImportIssue[],
  scope: SeedImportIssueScope,
  path: string,
) {
  const value = record[key];
  if (typeof value !== 'string' || !value.trim()) {
    pushIssue(issues, 'error', scope, path, `${path} 必须是非空字符串`);
    return '';
  }
  return value.trim();
}

function readStringArray(
  record: Record<string, unknown>,
  key: string,
  issues: SeedImportIssue[],
  scope: SeedImportIssueScope,
  path: string,
) {
  const value = record[key];
  if (!Array.isArray(value)) {
    pushIssue(issues, 'error', scope, path, `${path} 必须是字符串数组`);
    return [] as string[];
  }

  const invalidIndex = value.findIndex((item) => typeof item !== 'string');
  if (invalidIndex >= 0) {
    pushIssue(issues, 'error', scope, `${path}[${invalidIndex}]`, `${path} 里只能放字符串`);
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function readObjectArray(
  record: Record<string, unknown>,
  key: string,
  issues: SeedImportIssue[],
  scope: SeedImportIssueScope,
  path: string,
) {
  const value = record[key];
  if (!Array.isArray(value)) {
    pushIssue(issues, 'error', scope, path, `${path} 必须是对象数组`);
    return [] as Record<string, unknown>[];
  }

  const invalidIndex = value.findIndex((item) => !isRecord(item));
  if (invalidIndex >= 0) {
    pushIssue(issues, 'error', scope, `${path}[${invalidIndex}]`, `${path} 里只能放对象`);
  }
  return value.filter((item): item is Record<string, unknown> => isRecord(item));
}

function ensureUniqueIds(
  rows: { id: string }[],
  issues: SeedImportIssue[],
  scope: SeedImportIssueScope,
  path: string,
  label: string,
) {
  const seen = new Set<string>();
  rows.forEach((row, index) => {
    if (!row.id) return;
    if (seen.has(row.id)) {
      pushIssue(issues, 'error', scope, `${path}[${index}].id`, `重复的 ${label} id: ${row.id}`);
      return;
    }
    seen.add(row.id);
  });
}

function validateWorldbookDraft(raw: string, issues: SeedImportIssue[], existingWorldbookIds: Set<string>) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    pushIssue(issues, 'error', 'worldbook', 'worldbook JSON', 'JSON 解析失败', parseJsonLocation(raw, error));
    return null;
  }

  if (!isRecord(parsed)) {
    pushIssue(issues, 'error', 'worldbook', 'worldbook JSON', '需要一个完整的 worldbook JSON 对象');
    return null;
  }

  const id = readString(parsed, 'id', issues, 'worldbook', 'worldbook.id');
  const version = readString(parsed, 'version', issues, 'worldbook', 'worldbook.version');
  const title = readString(parsed, 'title', issues, 'worldbook', 'worldbook.title');
  const genre = readStringArray(parsed, 'genre', issues, 'worldbook', 'worldbook.genre');
  const tone = readStringArray(parsed, 'tone', issues, 'worldbook', 'worldbook.tone');
  const era = readString(parsed, 'era', issues, 'worldbook', 'worldbook.era');
  const locale = readString(parsed, 'locale', issues, 'worldbook', 'worldbook.locale');
  const author = readString(parsed, 'author', issues, 'worldbook', 'worldbook.author');
  const tags = readStringArray(parsed, 'tags', issues, 'worldbook', 'worldbook.tags');
  const worldRules = readStringArray(parsed, 'worldRules', issues, 'worldbook', 'worldbook.worldRules');
  const hardConstraints = readStringArray(parsed, 'hardConstraints', issues, 'worldbook', 'worldbook.hardConstraints');
  const socialNorms = readStringArray(parsed, 'socialNorms', issues, 'worldbook', 'worldbook.socialNorms');
  const narrativeBoundaries = readStringArray(
    parsed,
    'narrativeBoundaries',
    issues,
    'worldbook',
    'worldbook.narrativeBoundaries',
  );
  const eventSeeds = readStringArray(parsed, 'eventSeeds', issues, 'worldbook', 'worldbook.eventSeeds');
  const defaultScenePatterns = readStringArray(
    parsed,
    'defaultScenePatterns',
    issues,
    'worldbook',
    'worldbook.defaultScenePatterns',
  );
  const mapAssets = readStringArray(parsed, 'mapAssets', issues, 'worldbook', 'worldbook.mapAssets');

  const factions = readObjectArray(parsed, 'factions', issues, 'worldbook', 'worldbook.factions').map((row, index) => ({
    id: readString(row, 'id', issues, 'worldbook', `worldbook.factions[${index}].id`),
    name: readString(row, 'name', issues, 'worldbook', `worldbook.factions[${index}].name`),
    description: readString(row, 'description', issues, 'worldbook', `worldbook.factions[${index}].description`),
  }));

  const locations = readObjectArray(parsed, 'locations', issues, 'worldbook', 'worldbook.locations').map((row, index) => ({
    id: readString(row, 'id', issues, 'worldbook', `worldbook.locations[${index}].id`),
    name: readString(row, 'name', issues, 'worldbook', `worldbook.locations[${index}].name`),
    description: readString(row, 'description', issues, 'worldbook', `worldbook.locations[${index}].description`),
    tags: readStringArray(row, 'tags', issues, 'worldbook', `worldbook.locations[${index}].tags`),
    sceneHints: readStringArray(row, 'sceneHints', issues, 'worldbook', `worldbook.locations[${index}].sceneHints`),
  }));

  ensureUniqueIds(factions, issues, 'worldbook', 'worldbook.factions', '阵营');
  ensureUniqueIds(locations, issues, 'worldbook', 'worldbook.locations', '场景');

  if (!hardConstraints.length) {
    pushIssue(issues, 'error', 'worldbook', 'worldbook.hardConstraints', 'hardConstraints 不能为空');
  }
  if (!narrativeBoundaries.length) {
    pushIssue(issues, 'error', 'worldbook', 'worldbook.narrativeBoundaries', 'narrativeBoundaries 不能为空');
  }
  if (!locations.length && !defaultScenePatterns.length) {
    pushIssue(
      issues,
      'error',
      'worldbook',
      'worldbook.locations',
      'locations 和 defaultScenePatterns 至少要有一项提供内容',
    );
  }
  if (!eventSeeds.length) {
    pushIssue(issues, 'warning', 'worldbook', 'worldbook.eventSeeds', '没有事件种子时，舞台推进会比较单薄');
  }
  if (id && existingWorldbookIds.has(id)) {
    pushIssue(issues, 'error', 'worldbook', 'worldbook.id', `已有同名 worldbook: ${id}`);
  }

  return {
    id,
    version,
    title,
    genre,
    tone,
    era,
    locale,
    author,
    tags,
    worldRules,
    hardConstraints,
    socialNorms,
    narrativeBoundaries,
    factions,
    locations,
    eventSeeds,
    defaultScenePatterns,
    mapAssets,
  } satisfies Worldbook;
}

function validateCharacterDrafts(
  raw: string,
  issues: SeedImportIssue[],
  worldbook: Worldbook | null,
  existingCharacterIds: Set<string>,
) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    pushIssue(issues, 'error', 'characters', 'character cards JSON', 'JSON 解析失败', parseJsonLocation(raw, error));
    return [] as CharacterCard[];
  }

  const rows = Array.isArray(parsed) ? parsed : [parsed];
  if (!rows.length) {
    pushIssue(issues, 'error', 'characters', 'character cards JSON', '角色卡 JSON 数组不能为空');
    return [] as CharacterCard[];
  }

  const cards = rows.flatMap((row, index) => {
    if (!isRecord(row)) {
      pushIssue(issues, 'error', 'characters', `characterCards[${index}]`, '每一张角色卡都必须是对象');
      return [];
    }

    const id = readString(row, 'id', issues, 'characters', `characterCards[${index}].id`);
    const worldbookId = readString(row, 'worldbookId', issues, 'characters', `characterCards[${index}].worldbookId`);
    const name = readString(row, 'name', issues, 'characters', `characterCards[${index}].name`);
    const role = readString(row, 'role', issues, 'characters', `characterCards[${index}].role`);
    const tags = readStringArray(row, 'tags', issues, 'characters', `characterCards[${index}].tags`);
    const appearanceHints = readStringArray(row, 'appearanceHints', issues, 'characters', `characterCards[${index}].appearanceHints`);
    const personaTags = readStringArray(row, 'personaTags', issues, 'characters', `characterCards[${index}].personaTags`);
    const coreTraits = readStringArray(row, 'coreTraits', issues, 'characters', `characterCards[${index}].coreTraits`);
    const emotionalStyle = readString(row, 'emotionalStyle', issues, 'characters', `characterCards[${index}].emotionalStyle`);
    const socialStyle = readString(row, 'socialStyle', issues, 'characters', `characterCards[${index}].socialStyle`);
    const innerConflict = readString(row, 'innerConflict', issues, 'characters', `characterCards[${index}].innerConflict`);
    const likes = readStringArray(row, 'likes', issues, 'characters', `characterCards[${index}].likes`);
    const dislikes = readStringArray(row, 'dislikes', issues, 'characters', `characterCards[${index}].dislikes`);
    const softSpots = readStringArray(row, 'softSpots', issues, 'characters', `characterCards[${index}].softSpots`);
    const tabooTopics = readStringArray(row, 'tabooTopics', issues, 'characters', `characterCards[${index}].tabooTopics`);
    const publicFacts = readStringArray(row, 'publicFacts', issues, 'characters', `characterCards[${index}].publicFacts`);
    const privateFacts = readStringArray(row, 'privateFacts', issues, 'characters', `characterCards[${index}].privateFacts`);
    const knowledgeBoundaries = readStringArray(
      row,
      'knowledgeBoundaries',
      issues,
      'characters',
      `characterCards[${index}].knowledgeBoundaries`,
    );
    const scenePreferences = readStringArray(row, 'scenePreferences', issues, 'characters', `characterCards[${index}].scenePreferences`);
    const eventHooks = readStringArray(row, 'eventHooks', issues, 'characters', `characterCards[${index}].eventHooks`);
    const entryConditions = readStringArray(row, 'entryConditions', issues, 'characters', `characterCards[${index}].entryConditions`);
    const exitConditions = readStringArray(row, 'exitConditions', issues, 'characters', `characterCards[${index}].exitConditions`);
    const safetyRules = readStringArray(row, 'safetyRules', issues, 'characters', `characterCards[${index}].safetyRules`);
    const behaviorConstraints = readStringArray(
      row,
      'behaviorConstraints',
      issues,
      'characters',
      `characterCards[${index}].behaviorConstraints`,
    );
    const disclosureRules = readStringArray(
      row,
      'disclosureRules',
      issues,
      'characters',
      `characterCards[${index}].disclosureRules`,
    );

    let speechStyle: CharacterCard['speechStyle'] = {
      tone: '',
      verbosity: '',
      habitPhrases: [],
      avoidPhrases: [],
      cadenceHints: [],
    };
    const speechStyleRaw = row.speechStyle;
    if (!isRecord(speechStyleRaw)) {
      pushIssue(issues, 'error', 'characters', `characterCards[${index}].speechStyle`, 'speechStyle 必须是对象');
    } else {
      const tone = readString(speechStyleRaw, 'tone', issues, 'characters', `characterCards[${index}].speechStyle.tone`);
      const verbosity = readString(
        speechStyleRaw,
        'verbosity',
        issues,
        'characters',
        `characterCards[${index}].speechStyle.verbosity`,
      );
      const habitPhrases = readStringArray(
        speechStyleRaw,
        'habitPhrases',
        issues,
        'characters',
        `characterCards[${index}].speechStyle.habitPhrases`,
      );
      const avoidPhrases = readStringArray(
        speechStyleRaw,
        'avoidPhrases',
        issues,
        'characters',
        `characterCards[${index}].speechStyle.avoidPhrases`,
      );
      const cadenceHints = readStringArray(
        speechStyleRaw,
        'cadenceHints',
        issues,
        'characters',
        `characterCards[${index}].speechStyle.cadenceHints`,
      );
      speechStyle = {
        tone,
        verbosity,
        habitPhrases,
        avoidPhrases,
        cadenceHints,
      };

      if (!personaTags.length && !coreTraits.length && !habitPhrases.length) {
        pushIssue(
          issues,
          'error',
          'characters',
          `characterCards[${index}]`,
          'personaTags、coreTraits、speechStyle.habitPhrases 至少要补一项',
        );
      }
    }

    const unlockableSecrets = readObjectArray(
      row,
      'unlockableSecrets',
      issues,
      'characters',
      `characterCards[${index}].unlockableSecrets`,
    ).map((secret, secretIndex) => ({
      id: readString(secret, 'id', issues, 'characters', `characterCards[${index}].unlockableSecrets[${secretIndex}].id`),
      summary: readString(
        secret,
        'summary',
        issues,
        'characters',
        `characterCards[${index}].unlockableSecrets[${secretIndex}].summary`,
      ),
      unlockCondition: readString(
        secret,
        'unlockCondition',
        issues,
        'characters',
        `characterCards[${index}].unlockableSecrets[${secretIndex}].unlockCondition`,
      ),
    }));

    let relationshipDefaults: CharacterCard['relationshipDefaults'] = {
      trust: 0,
      affection: 0,
      tension: 0,
      familiarity: 0,
      stage: '',
    };
    const relationshipDefaultsRaw = row.relationshipDefaults;
    if (!isRecord(relationshipDefaultsRaw)) {
      pushIssue(
        issues,
        'error',
        'characters',
        `characterCards[${index}].relationshipDefaults`,
        'relationshipDefaults 必须是对象',
      );
    } else {
      ['trust', 'affection', 'tension', 'familiarity'].forEach((key) => {
        if (typeof relationshipDefaultsRaw[key] !== 'number') {
          pushIssue(
            issues,
            'error',
            'characters',
            `characterCards[${index}].relationshipDefaults.${key}`,
            `${key} 必须是数字`,
          );
        }
      });
      relationshipDefaults = {
        trust: typeof relationshipDefaultsRaw.trust === 'number' ? relationshipDefaultsRaw.trust : 0,
        affection: typeof relationshipDefaultsRaw.affection === 'number' ? relationshipDefaultsRaw.affection : 0,
        tension: typeof relationshipDefaultsRaw.tension === 'number' ? relationshipDefaultsRaw.tension : 0,
        familiarity: typeof relationshipDefaultsRaw.familiarity === 'number' ? relationshipDefaultsRaw.familiarity : 0,
        stage: readString(
          relationshipDefaultsRaw,
          'stage',
          issues,
          'characters',
          `characterCards[${index}].relationshipDefaults.stage`,
        ),
      };
    }

    if (!behaviorConstraints.length && !disclosureRules.length && !safetyRules.length) {
      pushIssue(
        issues,
        'error',
        'characters',
        `characterCards[${index}]`,
        'behaviorConstraints、disclosureRules、safetyRules 至少要补一项',
      );
    }
    if (privateFacts.length && !disclosureRules.length && !unlockableSecrets.length) {
      pushIssue(
        issues,
        'error',
        'characters',
        `characterCards[${index}].privateFacts`,
        'privateFacts 存在时，至少要提供 disclosureRules 或 unlockableSecrets',
      );
    }
    if (id && existingCharacterIds.has(id)) {
      pushIssue(issues, 'error', 'characters', `characterCards[${index}].id`, `已有同名角色卡: ${id}`);
    }
    if (!name) {
      pushIssue(issues, 'warning', 'characters', `characterCards[${index}]`, '建议补角色名，方便后续 session 选择');
    }

    return [
      {
        id,
        worldbookId,
        name,
        role,
        tags,
        appearanceHints,
        personaTags,
        coreTraits,
        emotionalStyle,
        socialStyle,
        innerConflict,
        speechStyle,
        likes,
        dislikes,
        softSpots,
        tabooTopics,
        publicFacts,
        privateFacts,
        unlockableSecrets,
        knowledgeBoundaries,
        scenePreferences,
        eventHooks,
        entryConditions,
        exitConditions,
        safetyRules,
        behaviorConstraints,
        disclosureRules,
        relationshipDefaults,
      },
    ];
  });

  ensureUniqueIds(cards, issues, 'characters', 'characterCards', '角色卡');

  if (!worldbook) {
    return cards;
  }

  const locationIds = new Set(worldbook.locations.map((row) => row.id));
  const eventSeedIds = new Set(worldbook.eventSeeds);

  cards.forEach((card, index) => {
    if (card.worldbookId !== worldbook.id) {
      pushIssue(
        issues,
        'error',
        'characters',
        `characterCards[${index}].worldbookId`,
        `worldbookId 必须和当前 worldbook.id 一致，预期 ${worldbook.id}，实际 ${card.worldbookId}`,
      );
    }

    const missingLocations = card.scenePreferences.filter((locationId) => !locationIds.has(locationId));
    if (missingLocations.length) {
      pushIssue(
        issues,
        'error',
        'characters',
        `characterCards[${index}].scenePreferences`,
        `引用了未知场景: ${missingLocations.join(', ')}`,
      );
    }

    const missingEventSeeds = card.eventHooks.filter((eventSeed) => !eventSeedIds.has(eventSeed));
    if (missingEventSeeds.length) {
      pushIssue(
        issues,
        'error',
        'characters',
        `characterCards[${index}].eventHooks`,
        `引用了未知事件种子: ${missingEventSeeds.join(', ')}`,
      );
    }
  });

  if (cards.length < 2) {
    pushIssue(issues, 'warning', 'characters', 'characterCards', '当前只有 1 张角色卡，可玩性会比较有限');
  }

  return cards;
}

export function validateSeedImportDrafts({
  worldbookDraft,
  characterDraft,
  existingWorldbookIds,
  existingCharacterIds,
}: ValidateImportDraftsArgs): SeedImportPreflight {
  const issues: SeedImportIssue[] = [];
  const worldbook = validateWorldbookDraft(worldbookDraft, issues, new Set(existingWorldbookIds));
  const characters = validateCharacterDrafts(characterDraft, issues, worldbook, new Set(existingCharacterIds));
  const errorCount = issues.filter((issue) => issue.severity === 'error').length;
  const warningCount = issues.length - errorCount;

  return {
    worldbook,
    characters,
    issues,
    errorCount,
    warningCount,
    canImport: Boolean(worldbook) && characters.length > 0 && errorCount === 0,
    summary: {
      worldbookId: worldbook?.id || '',
      worldbookTitle: worldbook?.title || '',
      locationCount: worldbook?.locations.length || 0,
      eventSeedCount: worldbook?.eventSeeds.length || 0,
      characterCount: characters.length,
    },
  };
}
