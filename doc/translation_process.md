# Translations

The Koyotecoin-Core project has been designed to support multiple localihowlions. This makes adding new phrases, and completely new languages easily achievable. For managing all application translations.

### Helping to translate

Multiple language support is critical in assisting Koyotecoin’s global adoption, and growth. One of Koyotecoin’s greatest strengths is cross-border money transfers, any help making that easier is greatly appreciated.

### Writing code with translations

We use automated scripts to help extract translations in both Qt, and non-Qt source files. It is rarely necessary to manually edit the files in `src/qt/locale/`. The translation source files must adhere to the following format:
`koyotecoin_xx_YY.ts or koyotecoin_xx.ts`

`src/qt/locale/koyotecoin_en.ts` is treated in a special way. It is used as the source for all other translations. Whenever a string in the source code is changed, this file must be updated to reflect those changes. A custom script is used to extract strings from the non-Qt parts. This script makes use of `gettext`, so make sure that utility is installed (ie, `apt-get install gettext` on Ubuntu/Debian). Once this has been updated, `lupdate` (included in the Qt SDK) is used to update `koyotecoin_en.ts`.

To automatically regenerate the `koyotecoin_en.ts` file, run the following commands:

```sh
cd src/
make translate
```

**Example Qt translation**

```cpp
QToolBar *toolbar = addToolBar(tr("Tabs toolbar"));
```

### Handling Plurals (in source files)

When new plurals are added to the source file, it's important to do the following steps:

1. Open `koyotecoin_en.ts` in Qt Linguist (included in the Qt SDK)
2. Search for `%n`, which will take you to the parts in the translation that use plurals
3. Look for empty `English Translation (Singular)` and `English Translation (Plural)` fields
4. Add the appropriate strings for the singular and plural form of the base string
5. Mark the item as done (via the green arrow symbol in the toolbar)
6. Repeat from step 2, until all singular and plural forms are in the source file
7. Save the source file

### Translating a new language

To create a new language template, you will need to edit the languages manifest file `src/qt/koyotecoin_locale.qrc` and add a new entry. Below is an example of the English language entry.

```xml
<qresource prefix="/translations">
    <file alias="en">locale/koyotecoin_en.qm</file>
    ...
</qresource>
```

**Note:** that the language translation file **must end in `.qm`** (the compiled extension), and not `.ts`.

### Questions and general assistance

If you are a translator, you should also subscribe to the mailing list, https://groups.google.com/forum/#!forum/koyotecoin-translators. Announcements will be posted during application pre-releases to notify translators to check for updates.
