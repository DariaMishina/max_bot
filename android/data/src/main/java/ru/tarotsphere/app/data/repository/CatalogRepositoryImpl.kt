package ru.tarotsphere.app.data.repository

import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.domain.model.Catalog
import ru.tarotsphere.app.domain.repository.CatalogRepository

class CatalogRepositoryImpl(
    private val api: AppApi,
) : CatalogRepository {
    override suspend fun catalog(): Catalog = apiCall { api.catalog().toDomain() }
}
