import js from "@eslint/js";

export default [
  {
    ignores: [".next/**", "node_modules/**"],
  },
  js.configs.recommended,
  {
    files: ["app/**/*.{js,jsx}"],
    rules: {
      "no-unused-vars": "off",
    },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        React: "readonly",
        fetch: "readonly",
        Date: "readonly",
        Intl: "readonly",
        Number: "readonly",
        Math: "readonly",
        console: "readonly",
      },
    },
  },
];
