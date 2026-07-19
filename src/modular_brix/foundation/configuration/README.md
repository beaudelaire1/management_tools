# configuration (F08)

Client customization without forking the core.

- Depends on: organizations (F01).
- Models: `Feature` (declared dependencies), `FeatureAssignment`, `SettingDefinition` (typed), `SettingValue`, `VocabularyTerm`.
- Services: `enable_feature` (dependency check), `set_setting`/`get_setting` (type validation, versioned defaults), `set_vocabulary_term`/`get_vocabulary_label`.
- Not yet implemented: `CustomFieldDefinition`/`CustomFieldValue`, configuration export.
