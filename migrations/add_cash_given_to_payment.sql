-- Afegeix la columna cash_given al model Payment
-- per guardar l'efectiu donat pel client

ALTER TABLE payments ADD COLUMN cash_given FLOAT DEFAULT 0.0;

-- Actualitza els pagaments existents amb valor per defecte
UPDATE payments SET cash_given = 0.0 WHERE cash_given IS NULL;
