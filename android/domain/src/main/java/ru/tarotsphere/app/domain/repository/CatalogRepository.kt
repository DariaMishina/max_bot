package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.Catalog

interface CatalogRepository {
    suspend fun catalog(): Catalog
}
